# Perfect Matching with minimum matching requirements on bicliques

## Pre-amble

### Perfect matching solution using max flow

Given a bipartite graph $G = (U \cup V, E)$, with $|V| = |U|$ and $\forall (u_i,v_i) \in E: u_i \in U, v_i \in V$, the perfect matching problem can be solved in polynomial time using a max flow formulation $D = ((N,A),s,t,c)$:

```math
\begin{aligned}
N &= U \cup V \cup \{s,t\} \\

A &= \{(s, i) | i \in U \} \cup \{(j, t) | j \in V \} \cup E \\

c_{ij} &= 1\;\;\; \forall (i,j) \in A
\end{aligned}
```

Solving this max flow problem gives the feasibility of the perfect matching if the flow $f$ saturates all outgoing edges of $s$ and incoming edges of $t$, with the flow going through the corresponding edges in E giving the corresponding matching $M$.

```math
\begin{aligned}
f_{sj} &= c_{sj}\; &\forall j \in U\\
f_{it} &= c_{it}\; &\forall i \in V\\
M &= \{(i,j) | (i,j) \in E\ \text{with}\ f_{ij} = 1\}
\end{aligned}
```

### Condensing the graph using bicliques

For any $K_{n,m}$ biclique $B = (U_b,V_b): U_b \subseteq U, V_b \subseteq V, n=|U_b|, m=|V_b|$ with $m,n > 1$ subgraph of $G$, we can compress the size of the flow problem graph by representing the biclique with an extra node $b$ in flow problem $D'$:

```math
\begin{aligned}

N' &= N \cup \{b\}\\

A' &= \left(A \setminus \{(i,j) | i \in U_b, j \in V_b\}\right) \cup \{(i,b) | i \in U_b \} \cup \{(b,j) | j \in V_b\}\\

c'_{ij} &= 1\;\ \forall (i,j) \in A'
\end{aligned}
```

The requirement for feasibility of a perfect matching stays the same(saturation of the s and t edges), and a corresponding matching within the biclique can be read out as any pairing of incoming and outgoing edges of $b$ in $f$.

## Min-flow bicliques

We define a min-flow biclique $B = (U_b,V_b,d_b)$ as requiring at least $c_b$ pairings to exist in the perfect matching. Using the above representation, this is trivially reducible into a max flow with demands problem by splitting $B$'s $b$ node into $b_{in}$ and $b_{out}$ with a demand edge $(b_{in},b_{out})$ between them of demand $d_b$ and capacity $c_b = \min (|U_b|,|V_b|)$. Trivially, $d_b \le c_b$, else the requirement would be impossible to fulfill.

The resulting max flow problem will have edges $(s,b_{out})$ and $(b_{in},t)$, each with capacity $c_b$, and the capacity of $(b_{in},b_{out})$ will be reduced by $d_b$.

To measure the feasibility of the matching, these new edges will need to be saturated as well, though the reading out of a perfect matching stays the same.

For a single min-flow biclique, this is trivially correct. However, complications arise in this reduction when multiple such constraints are added. Two non-overlapping constraints are trivially combined, since they don't interfere with each other's demand edge.

If multiple min-flow bicliques overlap, however, special care needs to be taken as each pairing can only contribute to a single edge demand while still using a polynomial-time solvable max flow representation. For any two overlapping min-flow bicliques $B_i = (U_i,V_i,d_i)$ and $B_j = (U_j,V_j,d_j)$, we identify the following special cases:

```math
\begin{align}
U_i \cap U_j = \empty &\lor V_i \cap V_j = \empty &\text{One-sided overlap}\\
U_i \subseteq U_j &\land V_i \subseteq V_j &\text{Complete subset}\\
\end{align}
```

If only one of $U_i \cap U_j$ and $V_i \cap V_j$ is non-empty(1), any matching pair can only be sent through at most one of the demand edges, thus keeping correctness intact.

If $U_i \cup V_i$ is a subset of $U_j \cup V_j$(2), then we need a little bit more work to fix the correctness. This relies on the "at least N" part of the constraint, using which we can just let these live side by side, but reduce $d_j$ by $d_i$ since all matching pairs of $B_i$ count towards $B_j$.

Other overlap cases turn out to be impossible to model with a max-flow problem.
