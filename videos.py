import sys
import os
import gurobipy as gp
from gurobipy import GRB

def read_input(filepath):
    print(f"Reading dataset: {filepath}...")
    with open(filepath, 'r') as f:
        lines = f.read().splitlines()

    # V: nb videos, E: nb endpoints, R: nb requests, C: nb caches, X: cache capacity
    V, E, R, C, X = map(int, lines[0].split())
    
    # Ligne 2: Tailles des vidéos
    video_sizes = list(map(int, lines[1].split()))
    
    # Lecture des Endpoints
    endpoints = []
    current_line_idx = 2
    for idx_e in range(E):
        Ld, K = map(int, lines[current_line_idx].split())
        current_line_idx += 1
        
        cache_connections = {}
        for _ in range(K):
            c_id, latency = map(int, lines[current_line_idx].split())
            cache_connections[c_id] = latency
            current_line_idx += 1
            
        endpoints.append({
            'id': idx_e,
            'Ld': Ld,
            'connections': cache_connections
        })
        
    requests = []
    for idx_r in range(R):
        v_id, e_id, n_count = map(int, lines[current_line_idx].split())
        requests.append({
            'id': idx_r,
            'video': v_id,
            'endpoint': e_id,
            'count': n_count
        })
        current_line_idx += 1
        
    print(f"Dataset loaded: {V} videos, {E} endpoints, {R} requests, {C} caches (Cap: {X}MB).")
    return V, E, R, C, X, video_sizes, endpoints, requests

def solve_videos(filepath):
    # 1. Lecture des données
    V, E, R, C, X, video_sizes, endpoints, requests = read_input(filepath)
    
    m = gp.Model("StreamingVideos")
    m.Params.MIPGap = 0.005  # 0.5% gap requis
    m.Params.OutputFlag = 1  # Afficher les logs Gurobi
    
    # --- Variables de décision ---
    # y[c, v] = 1 si la vidéo v est dans le cache c
    cached = {}
    for c in range(C):
        for v in range(V):
            if video_sizes[v] <= X:
                cached[c, v] = m.addVar(vtype=GRB.BINARY, name=f"cached_{c}_{v}")

    # x[r, c] = 1 si la requête r est servie par le cache c
    served = {}
    
    # Gain = (Latence_DC - Latence_Cache) * Nb_Requetes
    obj_expr = gp.LinExpr()
    
    for r_data in requests:
        r_id = r_data['id']
        v_id = r_data['video']
        e_id = r_data['endpoint']
        count = r_data['count']
        
        endpoint_data = endpoints[e_id]
        Ld = endpoint_data['Ld']
        
        for c_id, latency in endpoint_data['connections'].items():
            if latency < Ld:
                
                saving = (Ld - latency) * count
                
            
                served[r_id, c_id] = m.addVar(vtype=GRB.BINARY, name=f"served_{r_id}_{c_id}")
                
             
                obj_expr += saving * served[r_id, c_id]
                
               
                # served[r, c] <= cached[c, v]
                if (c_id, v_id) in cached:
                    m.addConstr(served[r_id, c_id] <= cached[c_id, v_id], name=f"link_{r_id}_{c_id}")
                else:
                    # Si la vidéo est trop grosse pour le cache, on force served à 0 (ou on ne crée pas la var)
                    m.addConstr(served[r_id, c_id] == 0)

    m.setObjective(obj_expr, GRB.MAXIMIZE)
    
    # --- Contraintes ---
    
    # 1. Capacité des caches
 
    for c in range(C):
        m.addConstr(
            gp.quicksum(video_sizes[v] * cached[c, v] for v in range(V) if (c, v) in cached) <= X,
            name=f"cap_{c}"
        )
        
    # 2. Chaque requête est servie par au plus un cache 
    print("Adding assignment constraints...")
    for r_data in requests:
        r_id = r_data['id']
        # Somme des 'served' pour cette requête <= 1
     
        e_id = r_data['endpoint']
        connected_caches = endpoints[e_id]['connections'].keys()
        
        vars_for_req = [served[r_id, c] for c in connected_caches if (r_id, c) in served]
        
        if vars_for_req:
            m.addConstr(gp.quicksum(vars_for_req) <= 1, name=f"assign_{r_id}")

    # 3. Écriture du fichier MPS (demandé dans la consigne)
    print("création de videos.mps")
    m.write("videos.mps")
    
    # 4. Résolution
    print("Résolution du model")
    m.optimize()
    
    # 5. Génération du fichier de sortie videos.out
    if m.SolCount > 0:
        print(f"La solutioni optimal est {m.ObjVal}")
        generate_output(C, V, cached)
    else:
        print("Pas de solu trouvé")

def generate_output(C, V, cached_vars):

    print("Création de videos.out")
    output_lines = []
    
    cache_content = {}
    
    for c in range(C):
        videos_in_cache = []
        for v in range(V):
            if (c, v) in cached_vars:
                
                if cached_vars[c, v].X > 0.5:
                    videos_in_cache.append(str(v))
        
        if videos_in_cache:
            cache_content[c] = videos_in_cache
            
   
    with open("videos.out", "w") as f:
        f.write(f"{len(cache_content)}\n")
        for c_id, videos in cache_content.items():
            f.write(f"{c_id} {' '.join(videos)}\n")
            
    print("File videos.out created successfully.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python videos.py [path/to/dataset]")
        sys.exit(1)
        
    dataset_path = sys.argv[1]
    if not os.path.exists(dataset_path):
        print(f"Error: File {dataset_path} not found.")
        sys.exit(1)
        
    solve_videos(dataset_path)