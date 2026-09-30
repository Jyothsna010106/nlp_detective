import networkx as nx
from pyvis.network import Network
import tempfile
import os

TYPE_THEMES = {
    "PERSON": {
        "color": {"background": "#9E5843", "border": "#E5A07C", "highlight": {"background": "#C87858", "border": "#F4DEC3"}},
        "icon": "👤",
        "shape": "box",
        "font": {"color": "#FFF8EA", "face": "DM Mono", "size": 13, "bold": True}
    },
    "ORG": {
        "color": {"background": "#806A3F", "border": "#D6B777", "highlight": {"background": "#A58A51", "border": "#FFF4D7"}},
        "icon": "🏢",
        "shape": "box",
        "font": {"color": "#FFF8EA", "face": "DM Mono", "size": 13, "bold": True}
    },
    "GPE": {
        "color": {"background": "#476D5B", "border": "#91B99B", "highlight": {"background": "#629277", "border": "#E0F0D8"}},
        "icon": "📍",
        "shape": "box",
        "font": {"color": "#F4F2E7", "face": "DM Mono", "size": 13, "bold": True}
    },
    "FAC": {
        "color": {"background": "#4D5962", "border": "#AAB9C1", "highlight": {"background": "#687983", "border": "#EDF4F3"}},
        "icon": "🏛️",
        "shape": "box",
        "font": {"color": "#F4F2E7", "face": "DM Mono", "size": 13, "bold": True}
    },
    "DEFAULT": {
        "color": {"background": "#3C4142", "border": "#9B9B8E", "highlight": {"background": "#5B6260", "border": "#F0E7D2"}},
        "icon": "📄",
        "shape": "box",
        "font": {"color": "#F4F2E7", "face": "DM Mono", "size": 12}
    }
}

def analyze_network_centrality(triplets: list[dict], processed_entities: list[dict]) -> tuple[str, list[dict], dict]:
    G = nx.DiGraph()
    ent_lookup = {e["text"].lower(): e["label"] for e in processed_entities}

    # Add Clean Entity Nodes and Directed Action Edges
    for t in triplets:
        s = t["Subject"]
        r = t["Relation"]
        o = t["Object"]

        s_type = t.get("Subject_Type", ent_lookup.get(s.lower(), "DEFAULT"))
        o_type = t.get("Object_Type", ent_lookup.get(o.lower(), "DEFAULT"))

        s_theme = TYPE_THEMES.get(s_type, TYPE_THEMES["DEFAULT"])
        o_theme = TYPE_THEMES.get(o_type, TYPE_THEMES["DEFAULT"])

        # Clean readable node labels with icons
        G.add_node(
            s,
            label=f" {s_theme['icon']}  {s} ",
            shape="box",
            margin=12,
            borderWidth=2,
            shadow={"enabled": True, "color": "rgba(0, 0, 0, 0.45)", "size": 12, "x": 0, "y": 5},
            color=s_theme["color"],
            font=s_theme["font"],
            title=f"Entity: {s} | Classification: {s_type}"
        )
        G.add_node(
            o,
            label=f" {o_theme['icon']}  {o} ",
            shape="box",
            margin=12,
            borderWidth=2,
            shadow={"enabled": True, "color": "rgba(0, 0, 0, 0.45)", "size": 12, "x": 0, "y": 5},
            color=o_theme["color"],
            font=o_theme["font"],
            title=f"Entity: {o} | Classification: {o_type}"
        )
        # Relationship arrow with contrasting badge
        G.add_edge(
            s, o,
            label=f"  {r}  ",
            arrows="to",
            color={"color": "rgba(214, 183, 119, 0.45)", "highlight": "#E5A07C", "hover": "#D6B777"},
            font={
                "color": "#E5D6B9",
                "size": 10,
                "face": "DM Mono, monospace",
                "background": "#181C1D",
                "strokeWidth": 0,
                "align": "horizontal"
            },
            width=1.5,
            selectionWidth=2.5,
            hoverWidth=2
        )

    if len(G.nodes) == 0:
        return "", [], None

    # Calculate Centrality
    G_undir = G.to_undirected()
    deg_centrality = nx.degree_centrality(G_undir)
    bet_centrality = nx.betweenness_centrality(G_undir)

    ranked_entities = []
    for node in G.nodes():
        node_clean = node.lower()
        ent_type = ent_lookup.get(node_clean, "ENTITY")
        deg_score = deg_centrality.get(node, 0)
        bet_score = bet_centrality.get(node, 0)
        connection_count = G_undir.degree(node)

        # 60% Degree (connections) + 40% Betweenness (bridge role)
        inv_score = round(((deg_score * 0.6) + (bet_score * 0.4)) * 100, 1)

        role = "Key Suspect / Hub" if deg_score >= 0.25 else ("Liaison / Broker" if bet_score > 0.1 else "Linked Entity")

        ranked_entities.append({
            "Entity": node,
            "Type": ent_type,
            "Direct Connections": f"{connection_count} links",
            "Network Role": role,
            "Involvement Score": inv_score
        })

    ranked_entities.sort(key=lambda x: x["Involvement Score"], reverse=True)

    # Pick the top PERSON or ORG as Primary Person of Interest
    top_poi = None
    for entry in ranked_entities:
        if entry["Type"] in ("PERSON", "ORG"):
            top_poi = entry
            break
    if not top_poi and ranked_entities:
        top_poi = ranked_entities[0]

    # Setup PyVis Canvas with Spacing & Force Physics (Prevents Clumping)
    net = Network(height="520px", width="100%", bgcolor="#141819", font_color="#E8E0CF", directed=True)
    net.from_nx(G)
    net.set_options("""
    {
            "nodes": {
                "borderWidth": 2,
                "shapeProperties": { "borderDashes": false, "useBorderWithImage": true },
                "scaling": { "min": 16, "max": 30 }
            },
            "physics": {
        "barnesHut": {
                    "gravitationalConstant": -6200,
                    "centralGravity": 0.12,
                    "springLength": 210,
                    "springConstant": 0.035,
                    "damping": 0.88,
                    "avoidOverlap": 0.9
        },
                "minVelocity": 0.5,
                "solver": "barnesHut",
                "stabilization": { "enabled": true, "iterations": 180, "fit": true }
      },
      "edges": {
        "smooth": {
          "type": "cubicBezier",
                    "roundness": 0.35
        },
        "arrows": {
                    "to": { "enabled": true, "scaleFactor": 0.65 }
                },
                "font": { "align": "middle" }
      },
      "interaction": {
        "hover": true,
        "zoomView": true,
        "navigationButtons": true,
                "keyboard": true,
                "tooltipDelay": 120,
                "hideEdgesOnDrag": false,
                "multiselect": false
      }
    }
    """)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as tmp:
        net.save_graph(tmp.name)
        with open(tmp.name, "r", encoding="utf-8") as f:
            html = f.read()
    os.remove(tmp.name)

    return html, ranked_entities, top_poi

def generate_graph_html(triplets: list[dict], processed_entities: list[dict]) -> str:
    html, _, _ = analyze_network_centrality(triplets, processed_entities)
    return html