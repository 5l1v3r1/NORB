import networkx as nx
import argparse
import json
import gzip
import os
import sys
from typing import List, Dict, Any

UNIQUE_ID = 0
NORB_PATH = "NORB/original_id_to_norb_id"
name_map_paths = {"tactic_map": "technique_tactic_map.json",
                  "technique_names": "technique_name_map.json",
                  "attack_map": "capec_technique_map.json",
                  "capec_names": "capec_names.json",
                  "capec_cwe": "capec_cwe_mapping.json",
                  "cwe_names": "cwe_names.json",
                  "cve_map": "cve_map_cpe_cwe_score.json",
                  "cve_map_2015_2020": "cve_map_cpe_cwe_score_2015_2020.json"}
id_dict_paths = {"tactic": "tactic_name_to_norb_id.json",
                 "technique": "technique_id_to_norb_id.json",
                 "capec": "capec_id_to_norb_id.json",
                 "cwe": "cwe_id_to_norb_id.json",
                 "cve": "cve_id_norb_id.json",
                 "cpe": "cpe_id_norb_id.json"}

def build_graph(save_path, input_data_folder, recent_cves=False):
    main_graph = nx.DiGraph()
    tactic_graph = add_tactic_technique_edges(main_graph, input_data_folder, save_path)
    attack_graph = add_capec_technique_edges(tactic_graph, input_data_folder, save_path)
    update_graph = add_capec_cwe_edges(attack_graph, input_data_folder, save_path)
    final_graph = add_cve_cpe_cwe(update_graph, recent_cves, input_data_folder, save_path)
    NORB_file_path = os.path.join(save_path, "NORB.json")
    save(final_graph, NORB_file_path)


def save(G, fname):
    json.dump(
        dict(
            nodes=[[n, G.nodes[n]] for n in G.nodes()],
            edges=[[u, v, G.edges[u, v]] for u, v in G.edges()],
        ),
        open(fname, "w"),
        indent=2,
    )


def get_unique_id():
    global UNIQUE_ID
    UNIQUE_ID += 1
    id_str = str(UNIQUE_ID)
    if len(id_str) != 5:
        id_str = id_str.zfill(5)
    return id_str


def load_json(data_file, input_data_folder):
    """
    data_file (str): data file to open, e.g. "tactic_map" or "attack_map"
    input_data_folder (str): folder path to input data

    Returns Python dictionary of JSON file using path associated with data_file
    """
    PATH = os.path.join(input_data_folder, name_map_paths[data_file])
    if PATH.lower().endswith('.json'):
        with open(PATH) as f:
            return json.load(f)
    elif PATH.lower().endswith('.gz'):
        with gzip.open(PATH, "rt", encoding="utf-8") as f:
            return json.load(f)


def write_json(data_type_ids, save_path):
    """
    data_type_ids (dict): maps string of data type to dict of data type id to norb id,
            e.g. {"technique": technique_id_to_norb_id, "capec": capec_id_to_norb_id}
    """
    os.makedirs(NORB_PATH, exist_ok=True)
    path_start = os.path.join(save_path, NORB_PATH)
    file_paths = id_dict_paths
    for data_type, id_dict in data_type_ids.items():
        PATH = os.path.join(path_start, file_paths[data_type])
        with open (PATH, "w") as f:
            json.dump(id_dict, f)


def add_tactic_technique_edges(graph, input_data_folder, save_path):
    tactic_map = load_json("tactic_map", input_data_folder)
    technique_names = load_json("technique_names", input_data_folder)
    technique_id_to_norb_id = {}
    # there are no internal tactic IDs so we map to tactic names
    tactic_name_to_norb_id = {}
    for technique in tactic_map:
        technique_original_id = technique
        if technique_original_id not in technique_id_to_norb_id:
            technique_norb_id = get_unique_id()
            technique_node_name = "technique_" + technique_norb_id
            technique_id_to_norb_id[technique_original_id] = technique_norb_id
            graph.add_node(
                technique_node_name,
                original_id=technique_original_id,
                datatype="technique",
                name=technique_names[technique_original_id],
                metadata={},
            )
        else:
            technique_norb_id = technique_id_to_norb_id[technique_original_id]
            technique_node_name = "technique_" + technique_norb_id

        tactics = tactic_map[technique]
        for tact in tactics:
            tactic_name = tact

            if tactic_name not in tactic_name_to_norb_id:
                tactic_norb_id = get_unique_id()
                tactic_node_name = "tactic_" + tactic_norb_id
                graph.add_node(
                    tactic_node_name,
                    original_id="",
                    datatype="tactic",
                    name=tact,
                    metadata={},
                )
                tactic_name_to_norb_id[tact] = tactic_norb_id
            else:
                tactic_norb_id = tactic_name_to_norb_id[tactic_name]
                tactic_node_name = "tactic_" + tactic_norb_id
            if not graph.has_edge(tactic_node_name, technique_node_name):
                graph.add_edge(tactic_node_name, technique_node_name)
            if not graph.has_edge(technique_node_name, tactic_node_name):
                graph.add_edge(technique_node_name, tactic_node_name)
    write_json({"technique": technique_id_to_norb_id, "tactic": tactic_name_to_norb_id}, save_path)
    return graph


def add_capec_technique_edges(graph, input_data_folder, save_path):
    attack_map = load_json("attack_map", input_data_folder)
    capec_names = load_json("capec_names", input_data_folder)
    technique_names = load_json("technique_names", input_data_folder)
    path = os.path.join(save_path, NORB_PATH, "technique_id_to_norb_id.json")
    with open(path, "r") as f:
        technique_id_to_norb_id = json.load(f)
    capec_id_to_norb_id = {}
    for capec in attack_map:
        capec_original_id = capec

        if capec_original_id not in capec_id_to_norb_id:
            if capec_original_id in capec_names:
                capec_real_name = capec_names[capec_original_id]
            else:
                capec_real_name = "Name not found"
            capec_norb_id = get_unique_id()
            capec_node_name = "capec_" + capec_norb_id
            graph.add_node(
                capec_node_name,
                original_id=capec_original_id,
                datatype="capec",
                name=capec_real_name,
                metadata={},
            )
            capec_id_to_norb_id[capec_original_id] = capec_norb_id

        else:
            capec_norb_id = capec_id_to_norb_id[capec_original_id]
            capec_node_name = "capec_" + capec_norb_id

        techniques = attack_map[capec]
        for tech in techniques:
            technique_original_id = tech
            if technique_original_id not in technique_id_to_norb_id:
                technique_norb_id = get_unique_id()
                technique_node_name = "technique_" + technique_norb_id
                if technique_original_id in technique_names:
                    technique_actual_name = technique_names[technique_original_id]
                else:
                    technique_actual_name = "Name not found"
                graph.add_node(
                    technique_node_name,
                    original_id=technique_original_id,
                    datatype="technique",
                    name=technique_actual_name,
                    metadata={},
                )
                technique_id_to_norb_id[technique_original_id] = technique_norb_id
            else:
                technique_norb_id = technique_id_to_norb_id[technique_original_id]
                technique_node_name = "technique_" + technique_norb_id

            if not graph.has_edge(technique_node_name, capec_node_name):
                graph.add_edge(technique_node_name, capec_node_name)
            if not graph.has_edge(capec_node_name, technique_node_name):
                graph.add_edge(capec_node_name, technique_node_name)
    write_json({"technique": technique_id_to_norb_id, "capec": capec_id_to_norb_id}, save_path)
    return graph


def add_capec_cwe_edges(graph, input_data_folder, save_path):
    # make capec and cwe node and add edge between the two of them
    capec_cwe = load_json("capec_cwe", input_data_folder)
    capec_names = load_json("capec_names", input_data_folder)
    cwe_names = load_json("cwe_names", input_data_folder)
    path = os.path.join(save_path, NORB_PATH, "capec_id_to_norb_id.json")
    with open(path, "r") as json_file:
        capec_id_to_norb_id = json.load(json_file)
    cwe_id_to_norb_id = {}
    capec_cwe_pairs = capec_cwe["capec_cwe"]
    for capec_node in capec_cwe_pairs:
        capec_original_id = capec_node
        if capec_original_id not in capec_id_to_norb_id:
            capec_norb_id = get_unique_id()
            capec_node_name = "capec_" + capec_norb_id
            if capec_original_id in capec_names:
                capec_real_name = capec_names[capec_original_id]
            else:
                capec_real_name = "Name not found"
            graph.add_node(
                capec_node_name,
                original_id=capec_original_id,
                datatype="capec",
                name=capec_real_name,
                metadata={},
            )
            capec_id_to_norb_id[capec_original_id] = capec_norb_id
        else:
            capec_norb_id = capec_id_to_norb_id[capec_original_id]
            capec_node_name = "capec_" + capec_norb_id

        cwes = capec_cwe_pairs[capec_node]["cwes"]
        for cwe in cwes:
            cwe_original_id = cwe
            if cwe_original_id not in cwe_id_to_norb_id:
                cwe_norb_id = get_unique_id()
                cwe_node_name = "cwe_" + cwe_norb_id
                if cwe_original_id in cwe_names:
                    cwe_real_name = cwe_names[cwe_original_id]
                else:
                    cwe_real_name = ""
                graph.add_node(
                    cwe_node_name,
                    original_id=cwe_original_id,
                    datatype="cwe",
                    name=cwe_real_name,
                    metadata={},
                )
                cwe_id_to_norb_id[cwe_original_id] = cwe_norb_id

            else:
                cwe_norb_id = cwe_id_to_norb_id[cwe_original_id]
                cwe_node_name = "cwe_" + cwe_norb_id
            if not graph.has_edge(capec_node_name, cwe_node_name):
                graph.add_edge(capec_node_name, cwe_node_name)
            if not graph.has_edge(cwe_node_name, capec_node_name):
                graph.add_edge(cwe_node_name, capec_node_name)
    write_json({"capec": capec_id_to_norb_id, "cwe": cwe_id_to_norb_id}, save_path)
    return graph


def add_cve_cpe_cwe(graph, recent_cves, input_data_folder, save_path):
    if recent_cves:
        cve_map = load_json("cve_map_2015_2020", input_data_folder)
    else:
        cve_map = load_json("cve_map", input_data_folder)
    cwe_names = load_json("cwe_names", input_data_folder)
    path = os.path.join(save_path, NORB_PATH, "cwe_id_to_norb_id.json")
    with open(path, "r") as f:
        cwe_id_to_norb_id = json.load(f)
    cve_id_to_norb_id = {}
    cpe_id_to_norb_id = {}
    for cve in cve_map:
        cve_original_id = cve
        if cve_original_id not in cve_id_to_norb_id:
            cve_norb_id = get_unique_id()
            cve_node_name = "cve_" + cve_norb_id
            graph.add_node(cve_node_name, datatype="cve", name="", original_id=cve_original_id,
                           metadata={"weight": cve_map[cve]["score"], "description": cve_map[cve]["description"]})
            cve_id_to_norb_id[cve_original_id] = cve_norb_id
        else:
            cve_norb_id = cve_id_to_norb_id[cve_original_id]
            cve_node_name = "cve_" + cve_norb_id

        for cpe in cve_map[cve]["cpes"]:
            _add_cpe_node(cpe, graph, cpe_id_to_norb_id, cve_node_name)
        for cwe in cve_map[cve]["cwes"]:
            cwe_original_id = cwe
            if not cwe.isalpha():
                if cwe_original_id not in cwe_id_to_norb_id:
                    cwe_norb_id = get_unique_id()
                    cwe_node_name = "cwe_" + cwe_norb_id
                    if cwe_original_id in cwe_names:
                        cwe_real_name = cwe_names[cwe_original_id]
                    else:
                        cwe_real_name = "Name not found"
                    graph.add_node(cwe_node_name, datatype="cwe", original_id=cwe_original_id, name=cwe_real_name, metadata={})
                    cwe_id_to_norb_id[cwe_original_id] = cwe_norb_id
                else:
                    cwe_norb_id = cwe_id_to_norb_id[cwe_original_id]
                    cwe_node_name = "cwe_" + cwe_norb_id

                if not graph.has_edge(cwe_node_name, cve_node_name):
                    graph.add_edge(cwe_node_name, cve_node_name)
                if not graph.has_edge(cve_node_name, cwe_node_name):
                    graph.add_edge(cve_node_name, cwe_node_name)
    write_json({"cwe": cwe_id_to_norb_id, "cve": cve_id_to_norb_id, "cpe": cpe_id_to_norb_id}, save_path)
    return graph


def parse_cpe(cpe_string):
    # splits cpe id into product, version, vendor
    dictionary = {"product": "", "vendor": "", "version": ""}
    cpe_values = cpe_string.split("cpe:2.3:")
    dictionary["vendor"] = cpe_values[1].split(":")[1]
    dictionary["product"] = cpe_values[1].split(":")[2]
    dictionary["version"] = cpe_values[1].split(":")[3]
    return dictionary


def _add_cpe_node(cpe, graph, cpe_id_to_norb_id, end_point):
    cpe_original_id = cpe
    if cpe_original_id not in cpe_id_to_norb_id:
        cpe_norb_id = get_unique_id()
        cpe_node_name = "cpe_" + cpe_norb_id
        cpe_meta_dict = parse_cpe(cpe_original_id)

        graph.add_node(
            cpe_node_name,
            datatype="cpe",
            name="",
            original_id=cpe_original_id,
            metadata=cpe_meta_dict,
        )
        cpe_id_to_norb_id[cpe_original_id] = cpe_norb_id
    else:
        cpe_norb_id = cpe_id_to_norb_id[cpe_original_id]
        cpe_node_name = "cpe_" + cpe_norb_id

    if not graph.has_edge(end_point, cpe_node_name):
        graph.add_edge(end_point, cpe_node_name)
    if not graph.has_edge(cpe_node_name, end_point):
        graph.add_edge(cpe_node_name, end_point)


def parse_args(args: List[str]) -> Dict[str, Any]:
    parser = argparse.ArgumentParser(description="Create NORB graph from threat data")
    parser.add_argument('--input_data_folder', type=str, required=True,
                        help='Folder path to input threat data')
    parser.add_argument('--save_path', type=str, required=True,
                        help='Folder path to save NORB graph and files, e.g. example_data/example_output_data')
    parser.add_argument('--only_recent_cves', action='store_true',
                        help='Make NORB with CVEs from 2015 to 2020 only')
    args = vars(parser.parse_args())
    return args


def main(**args: Dict[str, Any]) -> None:
    input_data_folder, save_path, recent_cves = args.values()
    build_graph(save_path, input_data_folder, recent_cves=recent_cves)


if __name__ == "__main__":
    kwargs = parse_args(sys.argv[1:])
    main(**kwargs)
