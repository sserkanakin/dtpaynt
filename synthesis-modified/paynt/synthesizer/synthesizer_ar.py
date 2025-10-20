import paynt.quotient.posmg
import paynt.synthesizer.synthesizer
import paynt.quotient.pomdp
import paynt.verification.property_result

import heapq
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

    def verify_family(self, family):
        self.quotient.build(family)

        # TODO include iteration_game in iteration? is it necessary?
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
        # Initialize priority queue with the root family
        # Using heapq min-heap, so we negate values to prioritize higher values
        # Format: (priority, counter, family) where counter ensures FIFO for same priorities
        families = []
        counter = 0
        
        # Initial family gets priority 0 (highest priority since we negate values)
        heapq.heappush(families, (0, counter, family))
        counter += 1

        iteration = 0
        while families:
            # Check resource limits (timeout, memory)
            if self.resource_limit_reached():
                logger.info("Resource limit reached, stopping synthesis")
                break
                
            iteration += 1
            # Only print every 100 iterations to reduce verbosity
            if iteration % 100 == 0:
                print(f"[Priority-Queue Search] Iteration {iteration}")
            
            priority, _counter, family = heapq.heappop(families)
            
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
            for subfamily in subfamilies:
                # Use parent's improving_value as heuristic (if available)
                # Otherwise use a default priority
                if (hasattr(family.analysis_result, 'improving_value') and 
                    family.analysis_result.improving_value is not None):
                    # Negate the value since heapq is a min-heap and we want max priority
                    subfamily_priority = -family.analysis_result.improving_value
                else:
                    # Default priority for families without improving_value
                    subfamily_priority = 0
                
                heapq.heappush(families, (subfamily_priority, counter, subfamily))
                counter += 1
                logger.debug(f"  Added subfamily with priority {subfamily_priority}")
                
        return self.best_assignment