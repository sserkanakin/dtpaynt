import paynt.synthesizer.statistic
import paynt.utils.timer

from typing import Any, Callable, Dict, Optional

import logging
import math
logger = logging.getLogger(__name__)


class FamilyEvaluation:
    '''Result associated with a family after its evaluation. '''
    def __init__(self, family, value, sat, policy):
        self.family = family
        self.value = value
        self.sat = sat
        self.policy = policy


class Synthesizer:

    # base filename (i.e. without extension) to export synthesis result
    export_synthesis_filename_base = None

    @staticmethod
    def choose_synthesizer(quotient, method, fsc_synthesis=False, storm_control=None):

        # hiding imports here to avoid mutual top-level imports
        import paynt.quotient.mdp
        import paynt.quotient.pomdp
        import paynt.quotient.decpomdp
        import paynt.quotient.mdp_family
        import paynt.quotient.posmg
        import paynt.synthesizer.synthesizer_onebyone
        import paynt.synthesizer.synthesizer_ar
        import paynt.synthesizer.synthesizer_cegis
        import paynt.synthesizer.synthesizer_hybrid
        import paynt.synthesizer.synthesizer_multicore_ar
        import paynt.synthesizer.synthesizer_pomdp
        import paynt.synthesizer.synthesizer_decpomdp
        import paynt.synthesizer.synthesizer_posmg
        import paynt.synthesizer.policy_tree
        import paynt.synthesizer.decision_tree

        if isinstance(quotient, paynt.quotient.pomdp_family.PomdpFamilyQuotient):
            logger.info("nothing to do with the POMDP sketch, aborting...")
            exit(0)
        if isinstance(quotient, paynt.quotient.mdp.MdpQuotient):
            return paynt.synthesizer.decision_tree.SynthesizerDecisionTree(quotient)
        # FSC synthesis for POMDPs
        if isinstance(quotient, paynt.quotient.pomdp.PomdpQuotient) and fsc_synthesis:
            return paynt.synthesizer.synthesizer_pomdp.SynthesizerPomdp(quotient, method, storm_control)
        # FSC synthesis for Dec-POMDPs
        if isinstance(quotient, paynt.quotient.decpomdp.DecPomdpQuotient) and fsc_synthesis:
            return paynt.synthesizer.synthesizer_decpomdp.SynthesizerDecPomdp(quotient)
        # Policy Tree synthesis for family of MDPs
        if isinstance(quotient, paynt.quotient.mdp_family.MdpFamilyQuotient):
            if method == "onebyone":
                return paynt.synthesizer.synthesizer_onebyone.SynthesizerOneByOne(quotient)
            else:
                return paynt.synthesizer.policy_tree.SynthesizerPolicyTree(quotient)
        # FSC synthesis for POSMGs
        if isinstance(quotient, paynt.quotient.posmg.PosmgQuotient) and fsc_synthesis:
            return paynt.synthesizer.synthesizer_posmg.SynthesizerPosmg(quotient)

        # synthesis engines
        if method == "onebyone":
            return paynt.synthesizer.synthesizer_onebyone.SynthesizerOneByOne(quotient)
        if method == "ar":
            return paynt.synthesizer.synthesizer_ar.SynthesizerAR(quotient)
        if method == "cegis":
            return paynt.synthesizer.synthesizer_cegis.SynthesizerCEGIS(quotient)
        if method == "hybrid":
            return paynt.synthesizer.synthesizer_hybrid.SynthesizerHybrid(quotient)
        if method == "ar_multicore":
            return paynt.synthesizer.synthesizer_multicore_ar.SynthesizerMultiCoreAR(quotient)
        raise ValueError("invalid method name")


    def __init__(self, quotient):
        self.quotient = quotient
        self.stat = None
        self.synthesis_timer = None
        self.explored = None
        self.best_assignment = None
        self.best_assignment_value = None

        self._progress_frontier_size: Optional[int] = None
        self._progress_families_evaluated: int = 0
        self._progress_improvements: int = 0
        self._progress_next_checkpoint: int = 1
        self._best_lower_bound: Optional[float] = None

        self._progress_observer: Optional[Callable[[Dict[str, Any]], None]] = None
        self._progress_metadata: Dict[str, Any] = {}
        self._progress_interval: Optional[float] = None
        self._last_progress_timestamp: float = 0.0

    @property
    def method_name(self):
        ''' to be overridden '''
        pass

    def time_limit_reached(self):
        if (self.synthesis_timer is not None and self.synthesis_timer.time_limit_reached()) or \
            paynt.utils.timer.GlobalTimer.time_limit_reached():
            logger.info("time limit reached, aborting...")
            return True
        return False

    def memory_limit_reached(self):
        if paynt.utils.timer.GlobalMemoryLimit.limit_reached():
            logger.info("memory limit reached, aborting...")
            return True
        return False

    def resource_limit_reached(self):
        return self.time_limit_reached() or self.memory_limit_reached()

    def set_optimality_threshold(self, optimum_threshold):
        if self.quotient.specification.has_optimality and optimum_threshold is not None:
            self.quotient.specification.optimality.update_optimum(optimum_threshold)
            logger.debug(f"optimality threshold set to {optimum_threshold}")

    def set_progress_observer(
        self,
        observer: Optional[Callable[[Dict[str, Any]], None]],
        interval_seconds: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._progress_observer = observer
        self._progress_interval = interval_seconds
        self._progress_metadata = metadata or {}
        self._last_progress_timestamp = 0.0
        self._progress_frontier_size = None
        self._progress_families_evaluated = 0
        self._progress_improvements = 0
        self._progress_next_checkpoint = 1
        self._best_lower_bound = None

    def _note_frontier_size(self, size: Optional[int]) -> None:
        self._progress_frontier_size = size if size is None else int(size)

    def _increment_families_evaluated(self) -> None:
        self._progress_families_evaluated += 1
        if (
            self._progress_observer is not None
            and self._progress_families_evaluated >= self._progress_next_checkpoint
        ):
            self._emit_progress("iteration")
            self._progress_next_checkpoint *= 2

    def _increment_improvements(self) -> None:
        self._progress_improvements += 1

    def _maybe_update_lower_bound(self, family) -> None:
        try:
            analysis_result = getattr(family, "analysis_result", None)
            if analysis_result is None:
                return
            opt_result = getattr(analysis_result, "optimality_result", None)
            if opt_result is None:
                return
            primary = getattr(opt_result, "primary", None)
            if primary is None:
                return
            value = getattr(primary, "value", None)
            if value is None:
                return
            bound = float(value)
        except Exception:
            return
        previous = self._best_lower_bound
        if previous is None or not math.isclose(bound, previous, rel_tol=1e-9, abs_tol=1e-9):
            self._best_lower_bound = bound
            if self._progress_observer is not None:
                self._emit_progress("lower_bound")

    def _collect_tree_metrics(self):
        def _decision_tree_stats(tree_obj):
            if tree_obj is None:
                return None
            depth = None
            total_nodes = None
            if hasattr(tree_obj, "get_depth"):
                try:
                    depth = tree_obj.get_depth()
                except Exception:
                    depth = None
            if hasattr(tree_obj, "collect_nodes"):
                try:
                    total_nodes = len(tree_obj.collect_nodes())
                except Exception:
                    total_nodes = None
            elif hasattr(tree_obj, "collect_nonterminals"):
                try:
                    internal = len(tree_obj.collect_nonterminals())
                    total_nodes = internal
                    if hasattr(tree_obj, "collect_terminals"):
                        total_nodes += len(tree_obj.collect_terminals())
                except Exception:
                    total_nodes = None
            if total_nodes is None and depth is None:
                return None
            return total_nodes, depth

        tree_candidates = [
            getattr(self, "best_tree", None),
            getattr(getattr(self, "quotient", None), "decision_tree", None),
        ]
        for candidate in tree_candidates:
            stats = _decision_tree_stats(candidate)
            if stats is not None:
                return stats

        policy_tree = getattr(self, "policy_tree", None)
        if policy_tree is None:
            return None, None

        try:
            total_nodes = len(policy_tree.collect_all()) if hasattr(policy_tree, "collect_all") else None

            def _compute_depth(node):
                if node is None or getattr(node, "is_leaf", False):
                    return 0
                return 1 + max((_compute_depth(child) for child in node.child_nodes), default=0)

            depth = _compute_depth(getattr(policy_tree, "root", None))
            return total_nodes, depth
        except Exception:
            return None, None

    def _snapshot_progress(self) -> Dict[str, Any]:
        elapsed = None
        if self.synthesis_timer is not None:
            try:
                elapsed = round(self.synthesis_timer.read(), 6)
            except Exception:
                elapsed = None
        tree_size, tree_depth = self._collect_tree_metrics()
        snapshot: Dict[str, Any] = {
            "timestamp": elapsed,
            "best_value": self.best_assignment_value,
            "tree_size": tree_size,
            "tree_depth": tree_depth,
            "frontier_size": self._progress_frontier_size,
            "families_evaluated": self._progress_families_evaluated,
            "improvement_count": self._progress_improvements,
            "lower_bound": self._best_lower_bound,
        }
        snapshot.update(self._progress_metadata)
        return snapshot

    def _emit_progress(self, event: str) -> None:
        if self._progress_observer is None:
            return
        snapshot = self._snapshot_progress()
        snapshot["event"] = event
        self._progress_observer(snapshot)
        if self.synthesis_timer is not None:
            try:
                self._last_progress_timestamp = self.synthesis_timer.read()
            except Exception:
                self._last_progress_timestamp = 0.0

    def maybe_emit_periodic_progress(self) -> None:
        if self._progress_observer is None or self._progress_interval is None:
            return
        if self.synthesis_timer is None or not self.synthesis_timer.running:
            return
        try:
            elapsed = self.synthesis_timer.read()
        except Exception:
            return
        if elapsed - self._last_progress_timestamp >= self._progress_interval:
            self._emit_progress("interval")

    def explore(self, family):
        self.explored += family.size

    def evaluate_all(self, family, prop, keep_value_only=False):
        ''' to be overridden '''
        pass

    def export_evaluation_result(self, evaluations, export_filename_base):
        ''' to be overridden '''
        pass

    def evaluate(self, family=None, prop=None, keep_value_only=False, print_stats=True):
        '''
        Evaluate each member of the family wrt the given property.
        :param family if None, then the design space of the quotient will be used
        :param prop if None, then the default property of the quotient will be used
            (assuming single-property specification)
        :param keep_value_only if True, only value will be associated with the family
        :param print_stats if True, synthesis statistic will be printed
        :param export_filename_base base filename used to export the evaluation results
        :returns a list of (family,evaluation) pairs
        '''
        if family is None:
            family = self.quotient.family
        if prop is None:
            prop = self.quotient.get_property()

        self.stat = paynt.synthesizer.statistic.Statistic(self)
        self.explored = 0
        logger.info("evaluation initiated, design space: {}".format(family.size))
        self.stat.start(family)
        evaluations = self.evaluate_all(family, prop, keep_value_only)
        self.stat.finished_evaluation(evaluations)
        logger.info("evaluation finished")

        if self.export_synthesis_filename_base is not None:
            self.export_evaluation_result(evaluations, self.export_synthesis_filename_base)

        if print_stats:
            self.stat.print()

        return evaluations


    def synthesize_one(self, family):
        ''' to be overridden '''
        pass

    def synthesize(
        self, family=None, optimum_threshold=None, keep_optimum=False, return_all=False, print_stats=True, timeout=None
    ):
        '''
        :param family family of assignment to search in
        :param families alternatively, a list of families can be given
        :param optimum_threshold known bound on the optimum value
        :param keep_optimum if True, the optimality specification will not be reset upon finish
        :param return_all if True and the synthesis returns a family, all assignments will be returned instead of an
            arbitrary one
        :param print_stats if True, synthesis stats will be printed upon completion
        :param timeout synthesis time limit, seconds
        '''
        if family is None:
            family = self.quotient.family
        if family.constraint_indices is None:
            family.constraint_indices = list(range(len(self.quotient.specification.constraints)))

        self.set_optimality_threshold(optimum_threshold)
        self.synthesis_timer = paynt.utils.timer.Timer(timeout)
        self.synthesis_timer.start()
        self._progress_frontier_size = None
        self._progress_families_evaluated = 0
        self._progress_improvements = 0
        self._progress_next_checkpoint = 1
        self._best_lower_bound = None
        if self._progress_observer is not None:
            self._emit_progress("start")
        self.stat = paynt.synthesizer.statistic.Statistic(self)
        self.explored = 0
        self.stat.start(family)
        self.synthesize_one(family)
        if self.best_assignment is not None and self.best_assignment.size > 1 and not return_all:
            self.best_assignment = self.best_assignment.pick_any()
        self.stat.finished_synthesis()
        if self.best_assignment is not None:
            logger.info("printing synthesized assignment below:")
            logger.info(self.best_assignment)

        if self.best_assignment is not None and self.best_assignment.size == 1:
            dtmc = self.quotient.build_assignment(self.best_assignment)
            result = dtmc.check_specification(self.quotient.specification)
            logger.info(f"double-checking specification satisfiability: {result}")

        if print_stats:
            self.stat.print()

        # Optional: export synthesized tree/policy if requested and available
        try:
            export_base = self.export_synthesis_filename_base
            if export_base:
                # Prefer an explicit best_tree (e.g., decision tree from quotient)
                best_tree = getattr(self, "best_tree", None)
                if best_tree is None:
                    best_tree = getattr(getattr(self, "quotient", None), "decision_tree", None)
                if best_tree is not None and hasattr(best_tree, "to_graphviz"):
                    tree = best_tree.to_graphviz()
                    # Ensure parent directory exists
                    import os
                    parent = os.path.dirname(export_base)
                    if parent:
                        os.makedirs(parent, exist_ok=True)
                    # Write .dot and render .png
                    with open(export_base + ".dot", "w") as f:
                        f.write(tree.source)
                    tree.render(export_base, format="png", cleanup=True)
        except Exception as e:
            logger.warning(f"Failed to export synthesis tree: {e}")

        assignment = self.best_assignment
        if self._progress_observer is not None:
            self._emit_progress("finished")
        if not keep_optimum:
            self.best_assignment = None
            self.best_assignment_value = None
            self.quotient.specification.reset()

        return assignment


    def run(self, optimum_threshold=None):
        return self.synthesize(optimum_threshold=optimum_threshold)
