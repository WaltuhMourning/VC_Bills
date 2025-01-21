import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import plotly.express as px
import os
from datetime import date
from openpyxl import load_workbook
from pyvis.network import Network
import tempfile
import streamlit.components.v1 as components

# ------------------------------------------
#         CONSTANTS / FILE REFERENCES
# ------------------------------------------
FILE_NAME = "VCR - All Enacted Law & Legislative Tracker.xlsx"
SHEET_NAME = "Enacted Federal Law (Ex. J.Res."

# ==========================================
#         DATA LOADING & PREP
# ==========================================
@st.cache_data
def load_data() -> pd.DataFrame:
    """
    Load, clean, and structure the spreadsheet data.
    """
    if not os.path.exists(FILE_NAME):
        st.error(f"File '{FILE_NAME}' not found in the current directory.")
        return pd.DataFrame()

    # Load data from Excel
    df = pd.read_excel(FILE_NAME, sheet_name=SHEET_NAME, engine="openpyxl")

    # Keep specific columns and rename for readability
    df = df[
        [
            "Author(s)",
            "Original Introduction Date:",
            "Main policy topic",
            "Current Link (Inc. Amndt, if applicable)",
            "Method of Enactment",
        ]
    ].copy()
    df.columns = ["Authors", "Date", "Policy Area", "Title and Link", "Enactment Method"]

    # Convert Date column to datetime
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")

    # Use openpyxl to extract actual hyperlink targets from the relevant column
    workbook = load_workbook(FILE_NAME)
    sheet = workbook[SHEET_NAME]
    links = []
    for row in sheet.iter_rows(min_row=2, max_row=sheet.max_row, min_col=4, max_col=4):
        cell = row[0]
        links.append(cell.hyperlink.target if cell.hyperlink else None)

    df["Link"] = links

    # Extract plain text for "Title" by removing embedded URLs from the string
    df["Title"] = df["Title and Link"].str.replace(r"http[^\s]+", "", regex=True).str.strip()

    # Explode authors by comma to facilitate filtering (e.g., "Sen. A, Sen. B" -> 2 rows)
    df = df.assign(Author=df["Authors"].str.split(",")).explode("Author")
    df["Author"] = df["Author"].str.strip()  # remove extra spaces

    return df

@st.cache_data
def get_filtered_data() -> pd.DataFrame:
    """
    Returns the cleaned data with valid dates only.
    """
    data = load_data()
    if not data.empty:
        # Drop rows with no valid Date
        data = data.dropna(subset=["Date"]).reset_index(drop=True)
    return data

# ==========================================
#         HELPER FUNCTIONS
# ==========================================
def generate_scatter_plot(
    data: pd.DataFrame,
    x_col: str,
    y_col: str,
    color_col: str,
    title: str,
    text_size: int = 12,
    annotate_points: bool = True
) -> px.scatter:
    """
    Generates a scatter plot with:
      - Hover info (including Method of Enactment).
      - Annotations that create clickable links (if annotate_points=True).
      - Consistent styling.
    """
    fig = px.scatter(
        data,
        x=x_col,
        y=y_col,
        color=color_col,
        size=[10] * len(data),  # fixed orb size
        hover_name="Title",
        hover_data={
            "Date": True,
            "Link": True,
            "Enactment Method": True,
            color_col: True,
        },
        labels={
            "Policy Area": "Policy Area",
            "Date": "Date Introduced",
            "Author": "Author",
            "Enactment Method": "Method of Enactment",
        },
        title=title,
    )
    fig.update_layout(
        autosize=True,
        height=700,
        font=dict(size=text_size),
        margin=dict(l=40, r=40, t=80, b=40),
    )

    # Optionally add clickable annotations for each data point
    if annotate_points:
        for i, row in data.iterrows():
            link = row.get("Link", None)
            x_val = row[x_col]
            y_val = row[y_col]
            title_text = row["Title"] or ""

            if pd.notna(link):
                annotation_text = f'<a href="{link}" target="_blank">{title_text}</a>'
            else:
                annotation_text = title_text  # no link if missing

            if annotation_text.strip():
                fig.add_annotation(
                    x=x_val,
                    y=y_val,
                    text=annotation_text,
                    showarrow=False,
                    yshift=10,  # shift label upward
                    font=dict(size=text_size - 2, color="blue"),
                )

    return fig

def display_results_table(df: pd.DataFrame):
    """
    Displays a summary and a nicely formatted table of the filtered results.
    """
    count = len(df)
    st.write(f"**Total matching records:** {count}")
    if count > 0:
        columns_to_show = [
            "Author",
            "Date",
            "Policy Area",
            "Enactment Method",
            "Title",
            "Link",
        ]
        st.dataframe(df[columns_to_show].reset_index(drop=True))
    else:
        st.info("No records match your selection.")

def create_network_graph(data: pd.DataFrame) -> Network:
    """
    Creates and returns an interactive PyVis force-directed Network graph 
    where each Author, Policy Area, and Bill Title is a node, with edges 
    showing relationships (Author -> Bill, Bill -> Policy Area).
    """
    net = Network(height="700px", width="100%", bgcolor="#222222", font_color="white")
    # Force Atlas 2 is often more stable visually:
    net.force_atlas_2based()

    added_nodes = set()

    for idx, row in data.iterrows():
        bill_title = row["Title"]
        author = row["Author"]
        policy_area = row["Policy Area"]
        link = row.get("Link", None)

        # Add Bill node
        if bill_title not in added_nodes:
            tooltip = f"<b>Bill</b>: {bill_title}"
            if link:
                tooltip += f"<br><a href='{link}' target='_blank'>Open Link</a>"
            net.add_node(bill_title, label=bill_title, title=tooltip, color="#ffa500")
            added_nodes.add(bill_title)

        # Add Author node
        if author and author not in added_nodes:
            net.add_node(author, label=author, title=f"<b>Author</b>: {author}", color="#1f78b4")
            added_nodes.add(author)

        # Add Policy node
        if policy_area and policy_area not in added_nodes:
            net.add_node(policy_area, label=policy_area, 
                         title=f"<b>Policy Area</b>: {policy_area}", color="#33a02c")
            added_nodes.add(policy_area)

        # Add edges
        if author:
            net.add_edge(author, bill_title, color="#bbbbbb")
        if policy_area:
            net.add_edge(bill_title, policy_area, color="#bbbbbb")

    return net

def render_network_graph(net: Network):
    """
    Renders the PyVis network graph in Streamlit by generating
    an HTML file and embedding it via an iframe.
    
    Uses net.write_html(..., notebook=False) to avoid the 'NoneType' error.
    """
    with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as tmp_file:
        temp_path = tmp_file.name

    # NOTE: This is the short-term fix that avoids .show()
    net.write_html(temp_path, notebook=False, open_browser=False)

    # Read the HTML into a string and then display via an iframe
    with open(temp_path, "r", encoding="utf-8") as f:
        html_content = f.read()

    components.html(html_content, height=700, scrolling=True)

def create_sankey_diagram(df: pd.DataFrame):
    """
    Creates a Sankey diagram with improved styling to reduce clutter.
    It visualizes the flow from Author -> Policy Area -> Enactment Method
    using plotly.graph_objects.
    """
    # 1) Extract unique authors, policy areas, methods
    authors = sorted(df["Author"].dropna().unique())
    policies = sorted(df["Policy Area"].dropna().unique())
    methods = sorted(df["Enactment Method"].dropna().unique())

    # 2) Build a single 'labels' list and track indices
    labels = list(authors) + list(policies) + list(methods)
    
    author_indices = {a: i for i, a in enumerate(authors)}
    policy_indices = {p: i + len(authors) for i, p in enumerate(policies)}
    method_indices = {
        m: i + len(authors) + len(policies)
        for i, m in enumerate(methods)
    }

    sources = []
    targets = []
    values = []

    # 3) Create edges from Author -> Policy Area
    for _, row in df.iterrows():
        author = row["Author"]
        policy = row["Policy Area"]
        if pd.notna(author) and pd.notna(policy):
            sources.append(author_indices[author])
            targets.append(policy_indices[policy])
            values.append(1)

    # 4) Create edges from Policy Area -> Method
    for _, row in df.iterrows():
        policy = row["Policy Area"]
        method = row["Enactment Method"]
        if pd.notna(policy) and pd.notna(method):
            sources.append(policy_indices[policy])
            targets.append(method_indices[method])
            values.append(1)

    # 5) Build the Sankey figure using graph_objects with improved styling
    fig = go.Figure(
        data=[
            go.Sankey(
                arrangement="snap",  # "snap" tends to give a clean layout
                node=dict(
                    pad=20,
                    thickness=20,
                    line=dict(color="#333", width=0.5),
                    label=labels,
                    color="#666",  
                    hovertemplate='%{label}<extra></extra>',  
                    # You can customize node text here if you like.
                ),
                link=dict(
                    source=sources,
                    target=targets,
                    value=values,
                    color="rgba(150,150,150,0.4)",  # Semi-transparent grey for links
                    hovertemplate=(
                        'Flow from %{source.label} to %{target.label} '
                        'has a value of %{value}<extra></extra>'
                    ),
                ),
            )
        ]
    )

    fig.update_layout(
        title_text="Sankey: Author → Policy Area → Method",
        font=dict(size=14),  # Increase overall font size
        height=600,
        margin=dict(l=50, r=50, t=50, b=50),
    )

    return fig

def create_timeline_plot(df: pd.DataFrame):
    """
    Creates a Plotly timeline showing the bills over time.
    We'll use the 'Date' as a single point. 
    We can replicate a timeline by setting start_date = Date, end_date = Date+1 day, for example.
    """
    # For a timeline, we typically need 'start' and 'end' columns
    temp_df = df.copy()
    temp_df["Start"] = temp_df["Date"]
    # Add 1 day as an arbitrary "end" so there's a small bar
    temp_df["End"] = temp_df["Date"] + pd.Timedelta(days=1)

    fig = px.timeline(
        temp_df,
        x_start="Start",
        x_end="End",
        y="Title",
        color="Author",
        hover_data=["Policy Area", "Enactment Method", "Link"],
        title="Timeline of Bills (1-Day Window)"
    )
    fig.update_yaxes(autorange="reversed")  # so earliest item is at top
    fig.update_layout(height=700)
    return fig

# ==========================================
#       MAIN APP
# ==========================================
def main():
    st.set_page_config(page_title="Enacted Federal Legislation Tracker", layout="wide")

    # ----- Sidebar with info -----
    with st.sidebar:
        st.title("About this App")
        st.markdown("""
        **Enacted Federal Legislation Tracker**  
        Version 2.0.  
        
        This enhanced app includes:  
        - **Filters** by Author, Policy, Enactment Method, and Date.  
        - **Scatter & Bar Charts** with advanced mode.  
        - **Network Graph** with physics-based layout (PyVis).  
        - **Sankey Diagram** for flow-based analysis.  
        - **Timeline** visualization.  
        
        *Tip*: Adjust filters to narrow down the data before using heavy visuals!
        """)
        # Optional disclaimers or instructions
        st.info("Make sure your data file is in the same folder.\n\nEnjoy exploring your legislative data!")

    st.title("Enacted Federal Legislation Tracker")

    # 1. Load Data
    data = get_filtered_data()
    if data.empty:
        st.error("No data available. Please ensure the file is available and correctly formatted.")
        return

    # 2. Introduction
    st.markdown(
        """
        This application **helps you explore and visualize** Enacted Federal Legislation records.
        
        **Basic steps**:  
        1. Use the radio buttons below to choose a primary filter approach.  
        2. Select from the dropdowns/slider to refine results.  
        3. See the filtered table and basic charts.  
        4. Expand advanced options for more complex filtering and alternative charts.

        ---
        """
    )

    # 3. Basic Filter UI
    st.subheader("Search / Filter Options")
    search_option = st.radio(
        "How would you like to search for bills?",
        ["Author", "Method of Enactment", "Policy Area", "Date Range"],
        index=0
    )

    # Prepare unique filter options
    authors = sorted(data["Author"].dropna().unique())
    policy_areas = sorted(data["Policy Area"].dropna().unique())
    methods = sorted(data["Enactment Method"].dropna().unique())
    min_date = data["Date"].min().date()
    max_date = data["Date"].max().date()

    # Default filters
    author_filter = []
    policy_filter = []
    enactment_filter = []
    date_range = (min_date, max_date)

    # One primary filter approach at a time
    if search_option == "Author":
        author_filter = st.multiselect("Select Author(s)", options=authors, default=[])
    elif search_option == "Method of Enactment":
        enactment_filter = st.multiselect("Select Method(s) of Enactment", options=methods, default=[])
    elif search_option == "Policy Area":
        policy_filter = st.multiselect("Select Policy Area(s)", options=policy_areas, default=[])
    elif search_option == "Date Range":
        date_range = st.slider(
            "Select Date Range",
            min_value=min_date,
            max_value=max_date,
            value=(min_date, max_date)
        )

    # Apply the chosen filters
    filtered_data = data[
        ((data["Author"].isin(author_filter)) | (len(author_filter) == 0)) &
        ((data["Policy Area"].isin(policy_filter)) | (len(policy_filter) == 0)) &
        ((data["Enactment Method"].isin(enactment_filter)) | (len(enactment_filter) == 0)) &
        (data["Date"] >= pd.to_datetime(date_range[0])) &
        (data["Date"] <= pd.to_datetime(date_range[1]))
    ]

    # 4. Display Filtered Results
    st.subheader("Filtered Results")
    display_results_table(filtered_data)

    # 5. Basic Scatter Plot
    if not filtered_data.empty:
        st.subheader("Basic Visualization")
        st.markdown(
            """
            **Tip**: Use the Plotly toolbar (top-right corner of the chart) to zoom, pan,
            or go full screen.  
            **Click** on a legend entry to hide/show certain series.
            """
        )
        fig = generate_scatter_plot(
            data=filtered_data,
            x_col="Policy Area",
            y_col="Date",
            color_col="Author",
            title="Policy Area vs. Date (Colored by Author)"
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No data to visualize. Please adjust your filters above.")

    with st.expander("Network Graph (Physics Simulation)"):
        st.markdown(
            """
            **Experience a dynamic, physics-based network**:
            - **Author** nodes (blue)
            - **Bill** nodes (orange)
            - **Policy Area** nodes (green)

            Drag them around to watch the “springs” in action.
            """
        )
        if not filtered_data.empty:
            net = create_network_graph(filtered_data)
            render_network_graph(net)
        else:
            st.info("No data to display in network graph. Please adjust the filters above.")
    # 6. Optional Additional Visualization (Bar Chart by Year)
    with st.expander("Show Bar Chart by Year", expanded=False):
        temp_df = filtered_data.copy()
        temp_df["Year"] = temp_df["Date"].dt.year
        year_counts = temp_df.groupby("Year")["Title"].count().reset_index()
        if not year_counts.empty:
            st.write("Number of Enacted Items per Year")
            fig_bar = px.bar(
                year_counts,
                x="Year",
                y="Title",
                labels={"Title": "Count of Enacted Items"},
                title="Enacted Items by Year",
            )
            st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.info("No data for bar chart. Please adjust your filters.")

    # 7. Advanced Mode
    with st.expander("Show Advanced Filters and Visualization", expanded=False):
        st.markdown(
            """
            **Advanced Mode**:
            - Combine multiple filters at once (e.g., multiple authors **AND** multiple policy areas).
            - Choose which columns go on the X-axis, Y-axis, or color dimension.
            - Adjust font sizes and toggle clickable labels for each orb.
            """
        )

        # Advanced Filters
        advanced_author_filter = st.multiselect(
            "Filter by Author",
            options=authors,
            default=author_filter
        )
        advanced_policy_filter = st.multiselect(
            "Filter by Policy Area",
            options=policy_areas,
            default=policy_filter
        )
        advanced_enactment_filter = st.multiselect(
            "Filter by Enactment Method",
            options=methods,
            default=enactment_filter
        )
        advanced_date_range = st.slider(
            "Select Date Range",
            min_value=min_date,
            max_value=max_date,
            value=date_range
        )

        # Chart styling control
        text_size = st.slider("Text Size in Chart", min_value=10, max_value=30, value=12, step=1)
        annotate_advanced = st.checkbox("Show Titles (Clickable) Above Each Orb?", value=True)

        # Create advanced filtered data
        advanced_filtered_data = data[
            ((data["Author"].isin(advanced_author_filter)) | (len(advanced_author_filter) == 0)) &
            ((data["Policy Area"].isin(advanced_policy_filter)) | (len(advanced_policy_filter) == 0)) &
            ((data["Enactment Method"].isin(advanced_enactment_filter)) | (len(advanced_enactment_filter) == 0)) &
            (data["Date"] >= pd.to_datetime(advanced_date_range[0])) &
            (data["Date"] <= pd.to_datetime(advanced_date_range[1]))
        ]

        # Display advanced filter results
        st.subheader("Advanced Filtered Results")
        display_results_table(advanced_filtered_data)

        # Let user choose columns for advanced scatter
        axis_options = ["Policy Area", "Date", "Author", "Enactment Method"]
        x_axis = st.selectbox("X-Axis", axis_options, index=0)
        y_axis = st.selectbox("Y-Axis", axis_options, index=1)
        color_col = st.selectbox("Color By", axis_options, index=2)

        # Generate advanced scatter plot
        if not advanced_filtered_data.empty:
            fig_advanced = generate_scatter_plot(
                data=advanced_filtered_data,
                x_col=x_axis,
                y_col=y_axis,
                color_col=color_col,
                title="Advanced Visualization",
                text_size=text_size,
                annotate_points=annotate_advanced
            )
            st.plotly_chart(fig_advanced, use_container_width=True)
        else:
            st.info("No data to visualize in Advanced Mode. Please update the filters.")

    # 8. Additional “Super-Cool” Visuals

    with st.expander("Sankey Diagram (Author → Policy Area → Method)"):
        if not filtered_data.empty:
            fig_sankey = create_sankey_diagram(filtered_data)
            st.plotly_chart(fig_sankey, use_container_width=True)
        else:
            st.info("No data to display for Sankey. Adjust your filters above.")

    with st.expander("Timeline View"):
        if not filtered_data.empty:
            fig_timeline = create_timeline_plot(filtered_data)
            st.plotly_chart(fig_timeline, use_container_width=True)
        else:
            st.info("No data to display in Timeline. Please adjust your filters.")

    # Optional: after everything, show a little flourish

# ==========================================
#     RUN THE APP
# ==========================================
if __name__ == "__main__":
    main()

