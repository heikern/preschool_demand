import streamlit as st
import pydeck as pdk
import json
from pathlib import Path
import ast
import pandas as pd

# Initialize selected_year in session state if not already set
if "selected_year" not in st.session_state:
    st.session_state["selected_year"] = 2024
selected_year = st.session_state["selected_year"]

st.set_page_config(layout="wide")

st.title("Subzone Level demand for Preschools in Singapore")

# Replace toggle checkbox with radio button for selecting heatmap mode
mode = st.radio(
    "Select Heatmap Mode", 
    ["mismatch of demand and supply", 
     "population of preschool aged residents"], 
    index=0, 
    key="toggle_heatmap"
)

# Automatically load the default GeoJSON file using a relative path
DEFAULT_GEOJSON_PATH = Path(__file__).parent / "data" / "2019_sub_zone_final_form.geojson"
try:
    with open(DEFAULT_GEOJSON_PATH, "r") as f:
        geojson_data = json.load(f)
except Exception as e:
    st.error("Failed to load the default GeoJSON file.")

# --- Normalization step ---
if mode == "mismatch of demand and supply":
    # For net_supply normalization using global extreme values across all years
    net_supply_values = []
    for feature in geojson_data.get("features", []):
        net_supply_str = feature["properties"].get("net_supply", "{}")
        try:
            net_supply_dict = ast.literal_eval(net_supply_str)
        except Exception:
            net_supply_dict = {}
        # Collect values across all years
        for val in net_supply_dict.values():
            if isinstance(val, (int, float)):
                net_supply_values.append(val)
    min_net = min(net_supply_values) if net_supply_values else 0
    max_net = max(net_supply_values) if net_supply_values else 1
else:
    # For population normalization using global extreme values across all years
    pop_values = []
    for feature in geojson_data.get("features", []):
        pop_str = feature["properties"].get("pop", "{}")
        try:
            pop_dict = ast.literal_eval(pop_str)
        except Exception:
            pop_dict = {}
        # Collect values across all years
        for val in pop_dict.values():
            if isinstance(val, (int, float)) and val > 0:
                pop_values.append(val)
    max_pop = max(pop_values) if pop_values else 1

# Preprocess features to add a color based on chosen metric for selected_year
for feature in geojson_data.get("features", []):
    # ...existing code to get net_supply_str and pop_str...
    if mode == "mismatch of demand and supply":
        net_supply_str = feature["properties"].get("net_supply", "{}")
        try:
            net_supply_dict = ast.literal_eval(net_supply_str)
        except Exception:
            net_supply_dict = {}
        net_supply_val = net_supply_dict.get(selected_year, 0)
        # Calculate norm then invert it
        norm = (net_supply_val - min_net) / (max_net - min_net) if max_net != min_net else 0
        new_norm = 1 - norm  # Inverted normalization
        red = int(255 - new_norm * (255 - 153))      # small values => dark red ([153,0,0]), large values => light yellow ([255,255,204])
        green = int(255 - new_norm * 255)
        blue = int(204 - new_norm * 204)
        color = [red, green, blue]
        feature["properties"]["net_supply_val"] = net_supply_val

        # **Add pop_value calculation here:**
        pop_str = feature["properties"].get("pop", "{}")
        try:
            pop_dict = ast.literal_eval(pop_str)
        except Exception:
            pop_dict = {}
        pop_value = pop_dict.get(selected_year, 0)
        feature["properties"]["pop_value"] = pop_value

        # Outline polygon in bold (thicker stroke) if net_supply is negative
        if net_supply_val < 0:
            feature["properties"]["line_width"] = 50  # Bold outline
        else:
            feature["properties"]["line_width"] = 5  # Normal outline

    else:
        pop_str = feature["properties"].get("pop", "{}")
        try:
            pop_dict = ast.literal_eval(pop_str)
        except Exception:
            pop_dict = {}
        pop_value = pop_dict.get(selected_year, 0)
        # Compute color using a gradient from light yellow [255,255,204] to dark red [153,0,0]
        if isinstance(pop_value, (int, float)) and pop_value > 0:
            norm = pop_value / max_pop
            red = int(255 - norm * (255 - 153))
            green = int(255 - norm * 255)
            blue = int(204 - norm * 204)
            color = [red, green, blue]
        else:
            color = [128, 128, 128]
        feature["properties"]["pop_value"] = pop_value
        feature["properties"]["line_width"] = 5  # Default stroke width
    # Override color to grey if population is 0 regardless of toggle
    if feature["properties"].get("pop_value") == 0:
        color = [128, 128, 128]
    feature["properties"]["color"] = color

# Filter out features with zero population before generating the heatmap
filtered_features = []
for feature in geojson_data.get("features", []):
    pop_str = feature["properties"].get("pop", "{}")
    try:
        pop_dict = ast.literal_eval(pop_str)
    except Exception:
        pop_dict = {}
    if pop_dict.get(selected_year, 0) == 0:
        continue
    filtered_features.append(feature)
geojson_data["features"] = filtered_features

# Define a GeoJsonLayer using Pydeck with dynamic fill color
geojson_layer = pdk.Layer(
    "GeoJsonLayer",
    geojson_data,
    opacity=0.8,
    stroked=True,
    filled=True,
    get_line_color=[0, 0, 139],  # Dark blue stroke color
    get_fill_color="properties.color",
    pickable=True,
    get_line_width="properties.line_width" # Dynamic stroke width
)

# Center the view over Singapore
view_state = pdk.ViewState(
    latitude=1.3521,
    longitude=103.8198,
    zoom=11,
    pitch=0,
)

# Define tooltip based on the toggle state
if mode == "mismatch of demand and supply":
    tooltip = {
    "html": f"""
    <div style="font-size:14px; line-height:1.2">
      <table style="border-collapse: collapse;">
         <tr>
            <td style="padding-right: 10px;"><b>Subzone:</b></td>
            <td>{{SUBZONE_N}}</td>
         </tr>
         <tr>
            <td style="padding-right: 10px;"><b>Preschool children Population ({selected_year}):</b></td>
            <td>{{pop_value}}</td>
         </tr>
         <tr>
            <td style="padding-right: 10px;"><b>Preschool Capacity:</b></td>
            <td>{{capacity}}</td>
         </tr>
         <tr>
            <td style="padding-right: 10px;"><b>Net Supply:</b></td>
            <td>{{net_supply_val}}</td>
         </tr>
      </table>
    </div>
    """
}
else:
    tooltip = {
    "html": f"""
    <div style="font-size:14px; line-height:1.2">
      <table style="border-collapse: collapse;">
         <tr>
            <td style="padding-right: 10px;"><b>Subzone:</b></td>
            <td>{{SUBZONE_N}}</td>
         </tr>
         <tr>
            <td style="padding-right: 10px;">
              <b>Preschool children Population ({selected_year}):</b>
            </td>
            <td>{{pop_value}}</td>
         </tr>
         <tr>
            <td style="padding-right: 10px;"><b>Preschool Capacity:</b></td>
            <td>{{capacity}}</td>
         </tr>
      </table>
    </div>
    """
}

# Create a deck with the GeoJsonLayer
deck = pdk.Deck(
    layers=[geojson_layer],
    initial_view_state=view_state,
    tooltip=tooltip
)

st.pydeck_chart(deck, height=700)

# Add color legend below the map based on the toggle state
if mode == "mismatch of demand and supply":
    st.markdown("""
    <div style="display:flex; align-items:center;">
        <div style="width:100px; height:20px; background: linear-gradient(to right, rgb(255,255,204), rgb(153,0,0)); margin-right:8px;"></div>
        <span>Gradient: High Net Supply (light yellow) to Low/Negative Net Supply (dark red) [Outlined subzones have demand>supply]</span>
    </div>
    """, unsafe_allow_html=True)
else:
    st.markdown("""
    <div style="display:flex; align-items:center;">
        <div style="width:100px; height:20px; background: linear-gradient(to right, rgb(255,255,204), rgb(153,0,0)); margin-right:8px;"></div>
        <span>Gradient: Low Population (light yellow) to High Population (dark red)</span>
    </div>
    """, unsafe_allow_html=True)

# Place the radio button below the map.
# Using the same key ensures session state is updated and triggers a re-run.
st.radio("Select Year", options=[2024, 2025, 2026, 2027, 2028], key="selected_year", horizontal=True)

# Add table widget below the map
# Extract properties for the table
table_data = []
for feature in geojson_data.get("features", []):
    props = feature["properties"]
    if props.get("pop_value") != 0:  # Only include subzones with non-zero populations
        if mode == "mismatch of demand and supply":
            table_data.append({
                "SUBZONE_N": props.get("SUBZONE_N"),
                "pop_value": props.get("pop_value"),
                "capacity": props.get("capacity"),
                "net_supply_val": props.get("net_supply_val", 0)  # Ensure net_supply_val is set to 0 if not available
            })
        else:
            table_data.append({
                "SUBZONE_N": props.get("SUBZONE_N"),
                "pop_value": props.get("pop_value"),
                "capacity": props.get("capacity"),
            })

df = pd.DataFrame(table_data)
if mode == "mismatch of demand and supply":
    df = df.sort_values(by="net_supply_val")  # sort from most negative to most positive
else:
    df = df.sort_values(by="pop_value", ascending=False)
    
st.dataframe(df)

# Display the current mode above the graph
st.subheader(f"Current Mode: {mode}")

# Add subzone selection widget and display its time-series chart.
subzone_list = [feature["properties"]["SUBZONE_N"] for feature in geojson_data["features"]]
selected_subzone = st.selectbox("Select Subzone", subzone_list, key="selected_subzone")
selected_feature = next((f for f in geojson_data["features"] if f["properties"]["SUBZONE_N"] == selected_subzone), None)
if selected_feature:
    import ast  # ensure ast is imported
    if mode == "mismatch of demand and supply":
        ns_str = selected_feature["properties"].get("net_supply", "{}")
        try:
            ns_dict = ast.literal_eval(ns_str)
        except Exception:
            ns_dict = {}
        times = sorted(ns_dict.items())
        data = {"Year": [int(year) for year, _ in times],
                "Net Supply": [value for _, value in times]}
        df = pd.DataFrame(data)
        chart = st.line_chart(df.set_index("Year"), use_container_width=True)
        chart.add_rows(df.set_index("Year"))
        st.write("X-axis: Years, Y-axis: Mismatch of Demand and Supply")
    else:
        pop_str = selected_feature["properties"].get("pop", "{}")
        try:
            pop_dict = ast.literal_eval(pop_str)
        except Exception:
            pop_dict = {}
        times = sorted(pop_dict.items())
        data = {"Year": [int(year) for year, _ in times],
                "Population": [value for _, value in times]}
        df = pd.DataFrame(data)
        chart = st.line_chart(df.set_index("Year"), use_container_width=True)
        chart.add_rows(df.set_index("Year"))
        st.write("X-axis: Years, Y-axis: population of preschool aged residents")

