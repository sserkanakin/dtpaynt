import paynt.quotient.posmg
import paynt.synthesizer.synthesizer
import paynt.quotient.pomdp
import paynt.verification.property_result

import heapq
import logging
import math
logger = logging.getLogger(__name__)

class SynthesizerAR(paynt.synthesizer.synthesizer.Synthesizer):

    DEFAULT_HEURISTIC = "value_only"
    DEFAULT_ALPHA = 0.1
    DEFAULT_EPSILON = 1e-9

    _CONFIG_HEURISTIC = DEFAULT_HEURISTIC
    _CONFIG_ALPHA = DEFAULT_ALPHA
    _CONFIG_EPSILON = DEFAULT_EPSILON

    @classmethod
    def configure_heuristic(cls, heuristic=None, alpha=None, epsilon=None):
        previous = (cls._CONFIG_HEURISTIC, cls._CONFIG_ALPHA, cls._CONFIG_EPSILON)
        if heuristic is not None:
            cls._CONFIG_HEURISTIC = heuristic
        if alpha is not None:
            cls._CONFIG_ALPHA = alpha
        if epsilon is not None:
            cls._CONFIG_EPSILON = epsilon
        updated = (cls._CONFIG_HEURISTIC, cls._CONFIG_ALPHA, cls._CONFIG_EPSILON)
        if updated != previous:
            logger.info(
                "Configured SynthesizerAR heuristic=%s alpha=%s epsilon=%s",
                cls._CONFIG_HEURISTIC,
                cls._CONFIG_ALPHA,
                cls._CONFIG_EPSILON,
            )

    def __init__(self, quotient):
        super().__init__(quotient)
        self.heuristic = self.__class__._CONFIG_HEURISTIC
        self.heuristic_alpha = self.__class__._CONFIG_ALPHA
        self.heuristic_epsilon = self.__class__._CONFIG_EPSILON

    @property
    def method_name(self):
        return "AR"

    def check_specification(self, family):
        ''' Check specification for mdp or smg based on self.quotient '''
        mdp = family.mdp

        if isinstance(self.quotient, paynt.quotient.posmg.PosmgQuotient):
            model = self.quotient.create_smg_from_mdp(mdp)
        else:
            model = mdp

        # check constraints
        admissible_assignment = None
        spec = self.quotient.specification
        if family.constraint_indices is None:
            family.constraint_indices = spec.all_constraint_indices()
        results = [None for _ in spec.constraints]
        for index in family.constraint_indices:
            constraint = spec.constraints[index]
            result = paynt.verification.property_result.MdpPropertyResult(constraint)
            results[index] = result

            # check primary direction
            result.primary = model.model_check_property(constraint)
            if result.primary.sat is False:
                result.sat = False
                break

            # check if the primary scheduler is consistent
            result.primary_selection,consistent = self.quotient.scheduler_is_consistent(mdp, constraint, result.primary.result)
            if consistent:
                assignment = family.assume_options_copy(result.primary_selection)
                dtmc = self.quotient.build_assignment(assignment)
                res = dtmc.check_specification(self.quotient.specification)
                if res.accepting_dtmc(self.quotient.specification):
                    result.sat = True
                    admissible_assignment = assignment

            # primary direction is SAT: check secondary direction to see whether all SAT
            result.secondary = model.model_check_property(constraint, alt=True)
            if mdp.is_deterministic and result.primary.value != result.secondary.value:
                logger.warning("WARNING: model is deterministic but min<max")
            if result.secondary.sat:
                result.sat = True
                continue

        spec_result = paynt.verification.property_result.MdpSpecificationResult()
        spec_result.constraints_result = paynt.verification.property_result.ConstraintsResult(results)

        # check optimality
        if spec.has_optimality and not spec_result.constraints_result.sat is False:
            opt = spec.optimality
            result = paynt.verification.property_result.MdpOptimalityResult(opt)

            # check primary direction
            result.primary = model.model_check_property(opt)
            if not result.primary.improves_optimum:
                # OPT <= LB
                result.can_improve = False
            else:
                # LB < OPT, check if LB is tight
                result.primary_selection,consistent = self.quotient.scheduler_is_consistent(mdp, opt, result.primary.result)
                result.can_improve = True
                if consistent:
                    # LB < OPT and it's tight, double-check the constraints and the value on the DTMC
                    result.can_improve = False
                    assignment = family.assume_options_copy(result.primary_selection)
                    dtmc = self.quotient.build_assignment(assignment)
                    res = dtmc.check_specification(self.quotient.specification)
                    if res.constraints_result.sat and spec.optimality.improves_optimum(res.optimality_result.value):
                        result.improving_assignment = assignment
                        result.improving_value = res.optimality_result.value
            spec_result.optimality_result = result

        spec_result.evaluate(family, admissible_assignment)
        family.analysis_result = spec_result

    def verify_family(self, family):
        self.quotient.build(family)

        # TODO include iteration_game in iteration? is it necessary?
        if isinstance(self.quotient, paynt.quotient.posmg.PosmgQuotient):
            self.stat.iteration_game(family.mdp.states)
        else:
            self.stat.iteration(family.mdp)

        self.check_specification(family)
        self._maybe_update_lower_bound(family)

    def update_optimum(self, family):
        ia = family.analysis_result.improving_assignment
        if ia is None:
            return
        if not self.quotient.specification.has_optimality:
            self.best_assignment = ia
            self.best_tree = getattr(self.quotient, "decision_tree", None)
            return
        iv = family.analysis_result.improving_value
        if not self.quotient.specification.optimality.improves_optimum(iv):
            return
        self.quotient.specification.optimality.update_optimum(iv)
        self.best_assignment = ia
        self.best_assignment_value = iv
        self.best_tree = getattr(self.quotient, "decision_tree", None)
        
        # Safely log with timer check
        elapsed_time = 0
        try:
            if paynt.utils.timer.GlobalTimer.global_timer is not None:
                elapsed_time = paynt.utils.timer.GlobalTimer.read()
        except Exception:
            pass

        logger.info(f"value {round(iv,4)} achieved after {round(elapsed_time,2)} seconds")
        if isinstance(self.quotient, paynt.quotient.pomdp.PomdpQuotient):
            self.stat.new_fsc_found(family.analysis_result.improving_value, ia, self.quotient.policy_size(ia))
        self._increment_improvements()
        self._emit_progress("improvement")

    def synthesize_one(self, family):
        # Initialize priority queue with the root family.
        # Using heapq min-heap, so negate priorities to emulate a max-heap.
        families = []
        counter = 0

        root_priority = self._sanitize_priority(self._heuristic_priority_for_family(None))
        heapq.heappush(families, (-root_priority, counter, family))
        counter += 1

        iteration = 0
        while families:
            self._note_frontier_size(len(families))
            # Check resource limits (timeout, memory)
            if self.resource_limit_reached():
                logger.info("Resource limit reached, stopping synthesis")
                break
            self.maybe_emit_periodic_progress()
                
            iteration += 1
            # Only print every 100 iterations to reduce verbosity
            if iteration % 100 == 0:
                print(f"[Priority-Queue Search] Iteration {iteration}")
            
            priority, _counter, family = heapq.heappop(families)
            
            self._increment_families_evaluated()
            self.verify_family(family)
            self.update_optimum(family)
            if not self.quotient.specification.has_optimality and self.best_assignment is not None:
                break
            # break
            if family.analysis_result.can_improve is False:
                self.explore(family)
                continue
            # undecided
            subfamilies = self.quotient.split(family)
            
            # Add subfamilies to priority queue with heuristic-based priorities
            parent_priority = self._heuristic_priority_for_family(family)
            for subfamily in subfamilies:
                subfamily_priority = self._sanitize_priority(parent_priority)
                heapq.heappush(families, (-subfamily_priority, counter, subfamily))
                counter += 1
                logger.debug(f"  Added subfamily with priority {subfamily_priority}")

            self._note_frontier_size(len(families))
                
        return self.best_assignment

    def _heuristic_priority_for_family(self, family):
        if family is None:
            return 0.0
        analysis = getattr(family, "analysis_result", None)
        if analysis is None:
            return 0.0

        if self.heuristic == "value_size":
            value = self._extract_value_for_analysis(analysis)
            tree_size = getattr(family, "size", None)
            if tree_size is None:
                tree_size = 0
            try:
                priority = float(self.heuristic_alpha) * float(value) + (1 - float(self.heuristic_alpha)) * float(tree_size)
            except (TypeError, ValueError):
                priority = self._extract_value_for_analysis(analysis)
            return priority if priority is not None else 0.0

        if self.heuristic in {"bounds_gap", "upper_bound"}:
            lb, ub = self._extract_bounds(analysis)
            if lb is None or ub is None:
                fallback = self._extract_value_for_analysis(analysis)
                return fallback if fallback is not None else 0.0
            gap = max(ub - lb, self.heuristic_epsilon)
            try:
                ratio = float(lb) / float(gap)
            except (TypeError, ValueError, ZeroDivisionError):
                ratio = 0.0
            return ratio

        value_only = self._extract_value_for_analysis(analysis)
        return value_only if value_only is not None else 0.0

    def _extract_value_for_analysis(self, analysis):
        value = getattr(analysis, "improving_value", None)
        if value is not None:
            return self._safe_float(value)
        optimum = getattr(analysis, "optimality_result", None)
        if optimum is not None:
            candidate = getattr(optimum, "improving_value", None)
            if candidate is not None:
                return self._safe_float(candidate)
            primary = getattr(optimum, "primary", None)
            primary_value = self._extract_result_value(primary)
            if primary_value is not None:
                return primary_value
        return self._safe_float(self.best_assignment_value)

    def _extract_bounds(self, analysis):
        optimum = getattr(analysis, "optimality_result", None)
        if optimum is None:
            return None, None
        primary = self._extract_result_value(getattr(optimum, "primary", None))
        secondary = self._extract_result_value(getattr(optimum, "secondary", None))
        if primary is None and secondary is None:
            value = getattr(optimum, "improving_value", None)
            primary = self._safe_float(value)
        if primary is None:
            primary = secondary
        if secondary is None:
            secondary = primary
        return primary, secondary

    def _extract_result_value(self, result_obj):
        if result_obj is None:
            return None
        direct = getattr(result_obj, "value", None)
        if direct is not None:
            maybe_float = self._safe_float(direct)
            if maybe_float is not None:
                return maybe_float
        alt = getattr(result_obj, "result", None)
        if alt is not None and isinstance(alt, (int, float)):
            return float(alt)
        getter = getattr(result_obj, "get_value", None)
        if callable(getter):
            try:
                return self._safe_float(getter())
            except Exception:
                return None
        return None

    @staticmethod
    def _safe_float(value):
        try:
            if value is None:
                return None
            if isinstance(value, (int, float)):
                return float(value)
            if hasattr(value, "__float__"):
                return float(value)
        except (TypeError, ValueError):
            return None
        return None

    @staticmethod
    def _sanitize_priority(priority):
        numeric = SynthesizerAR._safe_float(priority)
        if numeric is None or not math.isfinite(numeric):
            return 0.0
        return numeric