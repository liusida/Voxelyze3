import random
import numpy as np
import sys
from time import time

from cppn.networks import CPPN
from cppn.softbot import Genotype, Phenotype, Population
from cppn.tools.algorithms import Optimizer
from cppn.tools.utilities import make_material_tree
from cppn.objectives import ObjectiveDict
from cppn.tools.evaluation import evaluate_population
from cppn.tools.mutation import create_new_children_through_mutation
from cppn.tools.selection import pareto_selection


SEED = int(sys.argv[1])
random.seed(SEED)
np.random.seed(SEED)

GENS = 0  # 500 to 1000
POPSIZE = 2  # 49 or 99  # +1 for the randomly generated robot that is added each gen

IND_SIZE = (100, 100, 100)  # (100, 100, 100) 17 minutes for two guys on half a gpu

CHECKPOINT_EVERY = GENS+1  # ie. never  # GENS-1  # ie. last gen only

DIRECTORY = "."
start_time = time()


class MyGenotype(Genotype):
    """
    Defines a custom genotype, inheriting from base class Genotype.

    Each individual must have the following properties:

    The genotype consists of a single Compositional Pattern Producing Network (CPPN),
    with multiple inter-dependent outputs determining the material constituting each voxel
    (e.g. two types of active voxels, actuated in counter phase, and two passive voxel types, fat and bone)
    The material IDs in the phenotype mapping dependencies refer to a predefined palette of materials:
    (0: empty, 1: passiveSoft, 2: passiveHard, 3: active+, 4:active-)

    """
    def __init__(self):

        Genotype.__init__(self, orig_size_xyz=IND_SIZE)

        self.add_network(CPPN(output_node_names=["shape", "muscleOrTissue", "muscleType", "tissueType"]))

        self.to_phenotype_mapping.add_map(name="Data", tag="<Data>", func=make_material_tree,
                                          dependency_order=["shape", "muscleOrTissue", "muscleType", "tissueType"],
                                          output_type=int)

        self.to_phenotype_mapping.add_output_dependency(name="shape", dependency_name=None, requirement=None,
                                                        material_if_true=None, material_if_false="0")

        self.to_phenotype_mapping.add_output_dependency(name="muscleOrTissue", dependency_name="shape",
                                                        requirement=True, material_if_true=None, material_if_false=None)

        self.to_phenotype_mapping.add_output_dependency(name="tissueType", dependency_name="muscleOrTissue",
                                                        requirement=False, material_if_true="1", material_if_false="2")

        self.to_phenotype_mapping.add_output_dependency(name="muscleType", dependency_name="muscleOrTissue",
                                                        requirement=True, material_if_true="3", material_if_false="4")


class MyPhenotype(Phenotype):
    """
    Defines a custom phenotype, inheriting from the Phenotype class, which restricts the kind of robots that are valid

    """
    def is_valid(self):
        for name, details in self.genotype.to_phenotype_mapping.items():
            if np.isnan(details["state"]).any():
                print "INVALID: Nans in phenotype."
                return False

            if name == "Data":
                state = details["state"]

                # just make sure there is some material to simulate, even if all passive.
                if np.sum(state) == 0:
                    print "INVALID: Empty sim."
                    return False

        return True


# Now specify the objectives for the optimization.
# Creating an objectives dictionary
my_objective_dict = ObjectiveDict()

# Adding an objective named "fitness", which we want to maximize.
# This information is returned by Voxelyze in a fitness .xml file, with a tag named "distance"
my_objective_dict.add_objective(name="fitness", maximize=True, tag="<distance>")

# Add an objective to minimize the age of solutions: promotes diversity
my_objective_dict.add_objective(name="age", maximize=False, tag=None)


# Initializing a population of SoftBots
my_pop = Population(my_objective_dict, MyGenotype, MyPhenotype, pop_size=POPSIZE)

# quick test here to make sure evaluation is working properly:
# evaluate_population(my_pop)
# print [ind.fitness for ind in my_pop]

# Setting up our optimization
my_optimization = Optimizer(my_pop, pareto_selection, create_new_children_through_mutation, evaluate_population)

my_optimization.run(my_pop, max_gens=GENS, checkpoint_every=CHECKPOINT_EVERY, directory=DIRECTORY)

print "That took a total of {} minutes".format((time()-start_time)/60.)

# finally, record the history of best robot at end of evolution so we can play it back in VoxCad
my_pop.individuals = [my_pop.individuals[0]]
evaluate_population(my_pop, record_history=True)
# todo: this should be done every gen and there should be a script that grabs the best from a pickledPop and saves hist

