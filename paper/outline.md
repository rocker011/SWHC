# Paper Outline

Working title:

Semantic Wiener HyperConnector for Compact Evidence Assembly in Hypergraph RAG

## 1. Introduction

Hypergraph RAG improves n-ary fact representation, but query-time evidence
assembly can still be redundant or weakly organized.

## 2. Background

- Retrieval-augmented generation
- GraphRAG
- HyperGraphRAG
- Connector-style evidence assembly

## 3. Method

- Hypergraph representation
- Query-specific candidate subgraph
- Terminal-aware semantic Wiener objective
- Practical connector solver
- Context export

## 4. Experiments

- Datasets
- Baselines
- Metrics
- Implementation details

## 5. Results

- Answer quality
- Retrieval quality
- Token efficiency
- Ablations

## 6. Analysis

- Hop-level behavior
- Source coverage
- Answer exposure
- Failure cases

## 7. Limitations

- Dependence on upstream extraction quality
- Heuristic solver
- Answer spans can remain buried in source text

