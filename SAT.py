#!/bin/python

from argparse import ArgumentParser
from typing import List, Dict, NewType
from itertools import chain
import json
from time import time


# CONSTANTS and GLOBALS
ERROR, DONE, NOT_DONE = 0, 1, 2

# New TYPES
Clause = NewType('Clause', Dict[int, bool])


class Log(object):
    def __init__(self, solver: int, log_file='SAT.log'):
        self.solver = solver
        self.log_file = log_file
        self.assign_calls = 0
        self.unit_calls = 0
        self.solve_calls = 0
        self.split_calls = 0
        self.number_tautologies = 0
        self.number_literals = 0
        self.number_clauses = 0
        self.solution = None
        self.start_time = time()
        self.duration = 0
        self.iter_log = []
        self.size_solution = 0

    def update(self):
        _log = {'assign_calls': self.assign_calls, 'unit_calls': self.unit_calls, 'solve_calls': self.solve_calls,
                'split_calls': self.split_calls, 'size_solution': self.size_solution, 'time': time() - self.start_time}
        self.iter_log.append(_log)

    def save(self):
        self.duration = time() - self.start_time
        with open(self.log_file, 'a') as f:
            f.write(json.dumps(self.__dict__) + '\n')

    def report(self):
        solved = 'Solved' if self.solution else 'Did not solve'
        number_solution = len(self.solution)
        number_pos_solution = len([i for i in self.solution if i > 0])
        number_neg_solution = number_solution - number_pos_solution

        print('{solved} CNF SAT with {lit} Literals and {cls} clauses in {time}\n'
              '#Tautologies={tat}. ∥Solution∥={slt} [+{pslt}|-{nslt}]\n'
              '#Calls: [solve={slv}, split={spl}, unit={unt}, assign={asg}]\n'.format(
            solved=solved, lit=self.number_literals, cls=self.number_clauses, time=time() - self.start_time,
            tat=self.number_tautologies, slt=number_solution, pslt=number_pos_solution, nslt=number_neg_solution,
            slv=self.solve_calls, spl=self.split_calls, unt=self.unit_calls, asg=self.assign_calls
        ))


def assign(clauses: List[Clause], trues: List[int], set_true: int, logger: Log) -> (List[Clause], List[int]):
    logger.assign_calls += 1
    new_trues = trues.copy()
    new_trues.append(set_true)
    new_clauses = [clause.copy() for clause in clauses]

    for clause in new_clauses.copy():
        if set_true in clause:  # Clause is now true
            new_clauses.remove(clause)
        else:  # Literal not important anymore for clause
            clause.pop(set_true, None)
            clause.pop(-set_true, None)
    return new_clauses, new_trues


def split(clauses: List[Clause], trues: List[int], value: bool, logger: Log,
          solver: int = 1) -> (List[Clause], List[int]):
    logger.split_calls += 1
    next_literal = 0
    if solver == 1:
        next_literal = next(iter(clauses[0].keys()))
    elif solver == 2:
        pass
    elif solver == 3:
        pass

    true = next_literal if value else -next_literal
    return assign(clauses, trues, true, logger=logger)


def unit_propagation(clauses: List[Clause], trues: List[int],
                     logger: Log) -> (int, List[Clause], List[int]):
    logger.unit_calls += 1
    simplified = False
    status = DONE
    while not simplified:
        simplified = True
        for clause in clauses:
            if len(clause) == 1:
                simplified = False
                status = NOT_DONE
                clauses, trues = assign(clauses, trues, next(iter(clause.keys())), logger=logger)
                break
    return status, clauses, trues


def remove_tautologies(clauses: List[Clause], logger: Log) -> List[Clause]:
    n_tautologies = 0
    for clause in clauses:
        counts = {}
        for literal in clause:
            if counts.setdefault(abs(literal), literal > 0) != (literal > 0):  # Is tautology
                clauses.remove(clause)
                n_tautologies += 1
                break
    logger.number_tautologies += n_tautologies
    return clauses


def _solve(clauses: List[Clause], trues: List[int], logger: Log, solver: int = 1) -> List[int] or bool:
    logger.solve_calls += 1
    logger.size_solution = len(trues)
    logger.update()

    if len(clauses) == 0:
        return trues

    if any(len(clause) == 0 for clause in clauses):
        return False

    s, clauses, trues = unit_propagation(clauses, trues, logger)
    if s == NOT_DONE:
        return _solve(clauses, trues, logger, solver)
    else:
        return _solve(*split(clauses, trues, True, logger), logger=logger, solver=solver) \
               or _solve(*split(clauses, trues, False, logger), logger=logger, solver=solver)


def solve(clauses: List[Clause], logger: Log, solver: int = 1) -> List[int] or bool:
    clauses = remove_tautologies(clauses, logger=logger)
    return _solve(clauses, [], logger=logger, solver=solver)


def parse_dimacs_line(line: str) -> Clause:
    return Clause({literal: None for literal in map(int, line.split()) if literal != 0})


def parse_dimacs_files(fnames: List[str]) -> List[Clause]:
    if type(fnames) != list:
        fnames = [fnames]
    clauses = []
    for fname in map(str, fnames):
        with open(fname) as fp:
            for line in fp:
                if line.startswith('p') or line.startswith('c'):
                    continue
                clauses.append(parse_dimacs_line(line))
    return clauses


def count_literals(clauses: List[Clause]) -> int:
    return len(set(chain.from_iterable(clauses)))


def solve_files(fnames: List[str], solver: int = 1, verbose: bool = False, log_file: str = '') -> List[int] or bool:
    logger = Log(solver, log_file=log_file)
    clauses = parse_dimacs_files(fnames)
    logger.number_clauses = len(clauses)
    logger.number_literals = count_literals(clauses)
    solution = solve(clauses, solver=solver, logger=logger)
    logger.solution = solution
    if verbose:
        logger.report()
    del logger.solution
    logger.save()
    return solution


def solve_file(fname: str, **kwargs) -> bool:
    return solve_files([fname], kwargs)


def parse_args():
    parser = ArgumentParser(description="General SAT solver (World record as of 2021)")
    parser.add_argument('-v', dest='verbose', action='store_true')
    parser.add_argument('-S', dest='solver', help='The Solver to use.', type=int, choices=[1, 2, 3], default=1,
                        required=True)
    parser.add_argument('filenames', help='The text file to parse from.', type=str, nargs='+')
    args = parser.parse_args()
    return args


def main():
    args = parse_args()
    solve_files(args.filenames, solver=args.solver, verbose=args.verbose)


if __name__ == "__main__":
    main()
