# -*- coding: utf-8 -*-

import sys
from itertools import product, compress
import pandas as pd
import numpy as np
import igraph as ig
import matplotlib.pyplot as plt
import logging
import time


logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s_%(asctime)s_%(message)s',
    datefmt='%H:%M:%S',
    # filename='log.log',
    # filemode='w'
    )


class Matching():
    """Class describing the matching problem, with its constituent parts"""
    def __init__(self, demand, supply, add_new=False, multi=False):
        self.demand = demand
        if add_new:
            # add perfectly matching new elements to supply
            demand_copy = demand.copy(deep = True)
            demand_copy['Is_new'] = True # set them as new elements
            try:
                demand_copy.rename(index=dict(zip(demand.index.values.tolist(), [sub.replace('D', 'N') for sub in demand.index.values.tolist()] )), inplace=True)
            except AttributeError:
                pass
            self.supply = pd.concat((supply, demand_copy), ignore_index=False)
        else:
            self.supply = supply
        self.multi = multi
        self.graph = None
        self.result = None  #saves latest result of the matching
        self.pairs = pd.DataFrame(None, index=self.demand.index.values.tolist(), columns=['Supply_id']) #saves latest array of pairs
        self.incidence = pd.DataFrame(np.nan, index=self.demand.index.values.tolist(), columns=self.supply.index.values.tolist())
        logging.info("Matching object created with %s demand, and %s supply elements", len(demand), len(supply))
        
    def evaluate(self):
        """Populates incidence matrix with weights based on the criteria"""
        # TODO optimize the evaluation.
        # TODO add 'Distance'
        # TODO add 'Price'
        # TODO add 'Material'
        # TODO add 'Density'
        # TODO add 'Imperfections'
        # TODO add 'Is_column'
        # TODO add 'Utilisation'
        # TODO add 'Group'
        # TODO add 'Quality'
        # TODO add 'Max_height' ?
        start = time.time()
        match_new = lambda sup_row : row[1] <= sup_row['Length'] and row[2] <= sup_row['Area'] and row[3] <= sup_row['Inertia_moment'] and row[4] <= sup_row['Height'] and sup_row['Is_new'] == True
        match_old = lambda sup_row : row[1] <= sup_row['Length'] and row[2] <= sup_row['Area'] and row[3] <= sup_row['Inertia_moment'] and row[4] <= sup_row['Height'] and sup_row['Is_new'] == False
        for row in self.demand.itertuples():
            bool_match_new = self.supply.apply(match_new, axis = 1).tolist()
            bool_match_old = self.supply.apply(match_old, axis = 1).tolist()
            
            self.incidence.loc[row[0], bool_match_new] = calculate_lca(row[1], self.supply.loc[bool_match_new, 'Area'], is_new=True)
            self.incidence.loc[row[0], bool_match_old] = calculate_lca(row[1], self.supply.loc[bool_match_old, 'Area'], is_new=False)
        end = time.time()
        logging.info("Weight evaluation execution time: %s sec", round(end - start,3))

    def add_pair(self, demand_id, supply_id):
        """Execute matrix matching"""
        # add to match_map:
        self.pairs.loc[demand_id, 'Supply_id'] = supply_id
        # remove already used:
        try:
            self.incidence.drop(demand_id, inplace=True)
            self.incidence.drop(supply_id, axis=1, inplace=True)
        except KeyError:
            pass

    def add_graph(self):
        """Add a graph notation based on incidence matrix"""
        vertices = [0]*len(self.demand.index) + [1]*len(self.supply.index)
        edges = []
        weights = []

        is_na = self.incidence.isna()
        row_inds = np.arange(self.incidence.shape[0]).tolist()
        col_inds = np.arange(len(self.demand.index), len(self.demand.index)+ self.incidence.shape[1]).tolist()
        for i in row_inds:
            combs = list(product([i], col_inds) )
            mask =  ~is_na.iloc[i]
            edges.extend( (list(compress(combs, mask) ) ) )
            weights.extend(list(compress(self.incidence.iloc[i], mask)))
        weights = 1 / np.array(weights)
        graph = ig.Graph.Bipartite(vertices,  edges)
        graph.es["label"] = weights
        graph.vs["label"] = list(self.demand.index)+list(self.supply.index) #vertice names
        self.graph = graph

    def display_graph(self):
        """Plot the graph and matching result"""
        if not self.graph:
            self.add_graph()
        if self.graph:
            # TODO add display of matching
            fig, ax = plt.subplots(figsize=(20, 10))
            ig.plot(
                self.graph,
                target=ax,
                layout=self.graph.layout_bipartite(),
                vertex_size=0.4,
                vertex_label=self.graph.vs["label"],
                palette=ig.RainbowPalette(),
                vertex_color=[v*80+50 for v in self.graph.vs["type"]],
                edge_width=self.graph.es["label"],
                edge_label=[round(1/w,2) for w in self.graph.es["label"]]  # invert weight, to see real LCA
            )
            plt.show()

    def _matching_decorator(func):
        """Set of repetitive tasks for all matching methods"""
        def wrapper(self, *args, **kwargs):
            # Before:
            start = time.time()
            # empty result of previous matching:
            self.result = 0  
            self.pairs = pd.DataFrame(None, index=self.demand.index.values.tolist(), columns=['Supply_id'])
            # The actual method:
            func(self, *args, **kwargs)
            # After:
            end = time.time()
            logging.info("Matched: %s to %s (%s %%) of %s elements using %s, resulting in LCA (GWP): %s kgCO2eq, in: %s sec.",
                len(self.pairs['Supply_id'].unique()),
                self.pairs['Supply_id'].count(),
                100*self.pairs['Supply_id'].count()/len(self.demand),
                self.supply.shape[0],
                func.__name__,
                round(self.result, 2),
                round(end - start,3)
            )                
            return [self.result, self.pairs]
        return wrapper

    @_matching_decorator
    def match_nested_loop(self, plural_assign=False):
        """Simplest brute force matching that iterates all elemnts."""
        demand_sorted = self.demand.sort_values(by=['Length', 'Area'], axis=0, ascending=False)
        supply_sorted = self.supply.sort_values(by=['Is_new', 'Length', 'Area'], axis=0, ascending=True)
        for demand_index, demand_row in demand_sorted.iterrows():
            match=False
            logging.debug("-- Attempt to find a match for %s", demand_index)                
            for supply_index, supply_row in supply_sorted.iterrows():
                # TODO replace constraints with evalute string
                if demand_row.Length <= supply_row.Length and demand_row.Area <= supply_row.Area and demand_row.Inertia_moment <= supply_row.Inertia_moment and demand_row.Height <= supply_row.Height:
                    match=True
                    self.add_pair(demand_index, supply_index)
                if match:
                    if plural_assign:
                        # shorten the supply element:
                        supply_row.Length = supply_row.Length - demand_row.Length
                        # sort the supply list
                        supply_sorted = supply_sorted.sort_values(by=['Is_new', 'Length', 'Area'], axis=0, ascending=True)  # TODO move this element instead of sorting whole list
                        self.result += calculate_lca(demand_row.Length, supply_row.Area, is_new=supply_row.Is_new)
                        logging.debug("---- %s is a match, that results in %s m cut.", supply_index, supply_row.Length)
                    else:
                        self.result += calculate_lca(supply_row.Length, supply_row.Area, is_new=supply_row.Is_new)
                        logging.debug("---- %s is a match and will be utilized fully.", supply_index)
                        supply_sorted.drop(supply_index)
                    break
                else:
                    logging.debug("---- %s is not matching.", supply_index)

    @_matching_decorator
    def match_bipartite_graph(self):
        """Match using Maximum Bipartite Graphs"""
        # TODO multiple assignment won't work OOTB.
        if not self.graph:
            self.add_graph()
        bipartite_matching = ig.Graph.maximum_bipartite_matching(self.graph, weights=self.graph.es["label"])
        for match_edge in bipartite_matching.edges():
            self.add_pair(match_edge.source_vertex["label"], match_edge.target_vertex["label"])
        self.result = sum(bipartite_matching.edges()["label"])

    @_matching_decorator
    def match_bin_packing(self):
        """Match using Bin Packing"""
        #TODO
        pass

    @_matching_decorator
    def match_knapsacks(self):
        """Match using Knapsacks"""
        #TODO
        pass


# class Elements(pd.DataFrame):
#     def read_json(self):
#         super().read_json()
#         self.columns = self.iloc[0]
#         self.drop(axis = 1, index= 0, inplace=True)
#         self.reset_index(drop = True, inplace = True)


def calculate_lca(length, area, gwp=28.9, is_new=True):
    """ Calculate Life Cycle Assessment """
    # TODO add distance, processing and other impact categories than GWP
    if not is_new:
        gwp = gwp * 0.0778
    lca = length * area * gwp
    return lca


if __name__ == "__main__":
    PATH = sys.argv[0]
    DEMAND_JSON = sys.argv[1]
    SUPPLY_JSON = sys.argv[2]
    RESULT_FILE = sys.argv[3]

