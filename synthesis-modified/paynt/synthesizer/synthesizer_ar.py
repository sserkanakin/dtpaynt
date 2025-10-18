import paynt.quotient.posmg
import paynt.synthesizer.synthesizer
import paynt.quotient.pomdp
import paynt.verification.property_result
import heapq  # <-- Import heapq for the priority queue
import itertools
import math
import logging
logger = logging.getLogger(__name__)

class SynthesizerAR(paynt.synthesizer.synthesizer.Synthesizer):

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

        # ---------- Bounds and priority updates ----------
        # We interpret primary optimality value as:
        # - Maximizing: an admissible upper bound U(F) on achievable concrete value
        # - Minimizing: an admissible lower bound LB(F) on achievable concrete value (we still store it in upper_bound)
        # L(F) is best known concrete value within this family (if we found a consistent improving assignment)
        if self.quotient.specification.has_optimality:
            opt_res = family.analysis_result.optimality_result
            if opt_res is not None and opt_res.primary is not None:
                family.upper_bound = opt_res.primary.value
            # improving value is a concrete assignment value within F
            if family.analysis_result.improving_value is not None:
                lv = family.analysis_result.improving_value
                if family.lower_bound is None:
                    family.lower_bound = lv
                else:
                    # For maximizing: take max; for minimizing: take min
                    if self.quotient.specification.optimality.minimizing:
                        family.lower_bound = min(family.lower_bound, lv)
                    else:
                        family.lower_bound = max(family.lower_bound, lv)

    def verify_family(self, family):
        self.quotient.build(family)

        if isinstance(self.quotient, paynt.quotient.posmg.PosmgQuotient):
            self.stat.iteration_game(family.mdp.states)
        else:
            self.stat.iteration(family.mdp)

        self.check_specification(family)

    def update_optimum(self, family):
        ia = family.analysis_result.improving_assignment
        if ia is None:
            return
        if not self.quotient.specification.has_optimality:
            self.best_assignment = ia
            return
        iv = family.analysis_result.improving_value
        if not self.quotient.specification.optimality.improves_optimum(iv):
            return
        self.quotient.specification.optimality.update_optimum(iv)
        self.best_assignment = ia
        self.best_assignment_value = iv
        logger.info(f"value {round(iv,4)} achieved after {round(paynt.utils.timer.GlobalTimer.read(),2)} seconds")
        if isinstance(self.quotient, paynt.quotient.pomdp.PomdpQuotient):
            self.stat.new_fsc_found(family.analysis_result.improving_value, ia, self.quotient.policy_size(ia))

    def synthesize_one(self, family):
        # Best-first search with bound-gap priority, safe pruning, and simple dominance filtering.
        counter = itertools.count()

        # Internal helpers
        def family_signature(fam):
            return tuple(tuple(fam.hole_options(h)) for h in range(fam.num_holes))

        def compute_priority(fam, v_best, maximizing):
            # Explore eagerly if we lack critical bounds
            if fam.upper_bound is None:
                return float('inf')
            if maximizing:
                if fam.lower_bound is None:
                    return float('inf')
                return max(0.0, fam.upper_bound - fam.lower_bound)
            else:
                # For minimizing, fam.upper_bound stores a lower bound LB(F)
                if v_best is None or math.isinf(v_best):
                    return float('inf')
                return max(0.0, v_best - fam.upper_bound)

        def should_prune(fam, v_best, maximizing):
            if v_best is None:
                return False
            if fam.upper_bound is None:
                return False
            if maximizing:
                return fam.upper_bound <= v_best
            else:
                # fam.upper_bound is LB for minimizing
                return fam.upper_bound >= v_best

        # Initialize
        maximizing = True
        if self.quotient.specification.has_optimality:
            maximizing = self.quotient.specification.optimality.maximizing

        # Initial verification to populate bounds on the root
        self.verify_family(family)
        self.update_optimum(family)

        v_best = self.best_assignment_value
        if v_best is None:
            v_best = -math.inf if maximizing else math.inf

        # Priority queue stores (-priority, upper_bound for tie, -depth, counter, family)
        pq = []
        sig_seen = set()
        pruned_by_bound = 0
        dropped_by_dominance = 0
        pq_pushes = 0
        pq_pops = 0

        def push_if_useful(fam):
            nonlocal pq_pushes, dropped_by_dominance
            sig = family_signature(fam)
            if sig in sig_seen:
                return
            # Dominance filter: if fam ⊆ any queued family, drop fam
            for _, _, _, _, qfam in pq:
                if fam.subset_of(qfam):
                    dropped_by_dominance += 1
                    return
            # Compute priority and push
            pr = compute_priority(fam, self.best_assignment_value, maximizing)
            fam.priority = pr
            ub_tie = fam.upper_bound if fam.upper_bound is not None else (math.inf if maximizing else math.inf)
            depth_tie = fam.refinement_depth if hasattr(fam, 'refinement_depth') else 0
            heapq.heappush(pq, (-pr, ub_tie, -depth_tie, next(counter), fam))
            pq_pushes += 1
            sig_seen.add(sig)

        # Push root if not pruned
        if not should_prune(family, self.best_assignment_value, maximizing):
            push_if_useful(family)
        else:
            pruned_by_bound += 1

        iteration_count = 0
        while pq:
            if self.resource_limit_reached():
                break
            _, _, _, _, fam = heapq.heappop(pq)
            pq_pops += 1

            print(f"[Best-First] Iteration {iteration_count}: priority={fam.priority}, depth={fam.refinement_depth}, family={fam}")
            iteration_count += 1

            # If undecided, split and process children
            if fam.analysis_result is None:
                self.verify_family(fam)
            self.update_optimum(fam)
            if not self.quotient.specification.has_optimality and self.best_assignment is not None:
                break

            # Safety prune now that bounds may be updated
            if should_prune(fam, self.best_assignment_value, maximizing):
                pruned_by_bound += 1
                continue

            if fam.analysis_result.can_improve is False:
                self.explore(fam)
                continue

            # undecided => split and verify/push each child
            split_result = self.quotient.split(fam)
            # Support both [(score, fam), ...] and [fam, ...]
            if len(split_result) > 0 and isinstance(split_result[0], tuple):
                scored = split_result
            else:
                scored = [(None, sf) for sf in split_result]
            for _, subfam in scored:
                # Build and analyze to get bounds
                self.verify_family(subfam)
                self.update_optimum(subfam)
                if should_prune(subfam, self.best_assignment_value, maximizing):
                    pruned_by_bound += 1
                    continue
                push_if_useful(subfam)

        # Log basic stats
        logger.info(f"best-first exploration: pops={pq_pops}, pushes={pq_pushes}, pruned_by_bound={pruned_by_bound}, dominance_dropped={dropped_by_dominance}")
        return self.best_assignment