#!/bin/python

import sys
from itertools import chain
from collections import namedtuple, OrderedDict
from argparse import ArgumentParser


LitWrap = namedtuple('LitWrap', ['literal', 'sign'])
Node = namedtuple('Node', ['id', 'picked'])


class SplitException(BaseException):
    pass

class SimplifyException(BaseException):
    pass

class BacktrackException(BaseException):
    pass


class Bunch:
    def __init__(self, **kwds):
        self.__dict__.update(kwds)


class Literal(Bunch):
    def __init__(self, id: int, value=None):
        super().__init__(id=id, value=value)
        self.clauses = []

    def update(self, value):
        self.value = value

        # check for contridiction
        for clause in self.clauses:
            clause._number_not_falses = None
            if clause.value == False:
                raise BacktrackException


class Clause(Bunch):
    def __init__(self):
        super().__init__(litwraps=[], _number_not_falses=None, _value=None)

    def add(self, literal: Literal, sign: bool):
        self.litwraps.append(LitWrap(literal=literal, sign=sign))

    def is_tautology(self):
        counts = {}
        for litwrap in self.litwraps:
            if counts.setdefault(litwrap.literal.id, litwrap.sign) != litwrap.sign:
                return True
        return False

    @property
    def value(self):
        if self._value != None:
            return self._value
        has_none = False
        for litwrap in self.litwraps:
            if litwrap.literal.value == None:
                has_none = True
                continue
            value = not(litwrap.literal.value ^ litwrap.sign)
            if value:
                return True
        if has_none:
            return None
        else:
            return False;

    @property
    def number_not_falses(self):
        if self._number_not_falses == None:
            self._number_not_falses = 0
            for litwrap in self.litwraps:
                if litwrap.literal.value == None:
                    self._number_not_falses += 1
                else:
                    self._number_not_falses += not(litwrap.literal.value ^ litwrap.sign)
        return self._number_not_falses


class Solver(object):
    def __init__(self):
        self.clauses = []
        self.literals = {}
        self.log = []
        self.pivot = -1
        self.next_call = None

    def print(self):
        print('NClauses: {}, NLiterals: {}'.format(len(self.clauses), len(self.literals)))

    def number_of_none_literals(self):
        n = 0
        for literal in self.literals.values():
            n += literal.value == None
        return n

    def check_done(self):
        if all([clause.value for clause in self.clauses]):
            print('Le finish')
            exit(0)

    def solve(self):
        self.fix_tautologies()
        self.next_call = self.simplify
        while self.next_call:
            self.next_call()


    def fix_tautologies(self):
        for clause in self.clauses:
            if clause.is_tautology():
                clause._value = True

    def simplify(self):
        try:
            simplified = False
            while not simplified:
                simplified = self._simplify()
            self.check_done()
            self.next_call = self.split
        except BacktrackException:
            self.next_call = self.backtrack
            return

    def _simplify(self):
        for clause in self.clauses:
            if clause.number_not_falses != 1:
                continue
            # We got a uni clause
            for litwrap in clause.litwraps:
                if litwrap.literal.value == None:
                    litwrap.literal.update(litwrap.sign)
                    self.log.append(Node(id=litwrap.literal.id, picked=False))
                    return False
        return True

    def split(self):
        _pivot = self.next_pivot()
        print('Split: {} #Nones: {}, |Log|: {}, pivot: {}, true clauses: {}'.format(_pivot, self.number_of_none_literals(), len(self.log), self.pivot, sum([1 for c in self.clauses if c.value == True])))
        if _pivot == None:
            self.next_call = self.backtrack
            return
        self.pivot = _pivot
        self.literals[self.pivot].update(False)
        self.log.append(Node(id=self.pivot, picked=True))
        self.next_call = self.simplify

    def next_pivot(self):
        for id, literal in self.literals.items():
            if id <= self.pivot or literal.value != None:
                continue
            return int(id)

    def backtrack(self):
        pivot_literal = self.literals[self.pivot]
        if pivot_literal.value == False:
            print('Backtrack pivot {} was false'.format(self.pivot))
            self.reverse_changes_until(pivot_literal.id)
            self.log.append(Node(id=pivot_literal.id, picked=True))
            pivot_literal.update(True)
            self.next_call = self.simplify
        elif pivot_literal.id > 1: # Pivot was true:
            print('Backtrack pivot {} was true'.format(self.pivot))
            self.reverse_changes_until(pivot_literal.id)
            self.pivot = self.find_last_pivot()
            self.next_call = self.backtrack
        else:
            print('EMPTY')
            exit(0)

    def find_last_pivot(self):
        for node in reversed(self.log):
            if not node.picked:
                continue
            return int(node.id)

    def reverse_changes_until(self, id: int):
        # print('Pivot: {}, #Nones: {}, |Log|: {}, Σ {}'.format(self.pivot, self.number_of_none_literals(), len(self.log), self.number_of_none_literals() + len(self.log)))
        # print(' '.join([str(node.id) for node in self.log]))
        it = reversed(self.log)
        try:
            node = next(it)
            while True:
                self.literals[node.id].update(None)
                if int(node.id) == int(id):
                    return self.log.pop()
                node = next(it)
                self.log.pop()
        except StopIteration:
            print(' '.join([str(node.id) for node in self.log]))

    def add_sat_file(self, fname):
        _literals = {}
        with open(fname) as fp:
            for line in fp:
                if line.startswith('p') or line.startswith('c'):
                    continue
                clause = Clause()
                clauseid = len(self.clauses)
                for c in line.split():
                    literal = float(c)
                    literal, sign = abs(literal), literal > 0
                    if literal == 0:
                        self.clauses.append(clause)
                        break

                    _literals.setdefault(literal, Literal(literal))
                    _literals[literal].clauses.append(clause)
                    clause.add(literal=_literals[literal], sign=sign)
        self.literals = OrderedDict(sorted(chain(self.literals.items(), _literals.items()), key=lambda x: x[0]))


def parse_args():
    parser = ArgumentParser(description="General SAT solver (World record as of 2021)")
    parser.add_argument('-S', dest='solver', help='The Solver to use.', type=int, choices=[1,2,3], default=1, required=True)
    parser.add_argument('filename', help='The text file to parse from.')
    args = parser.parse_args()
    return args

def main():
    args = parse_args()
    solver = Solver()
    solver.add_sat_file(args.filename)
    solver.solve()

if __name__ == "__main__":
    main()
