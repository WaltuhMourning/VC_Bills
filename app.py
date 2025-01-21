import streamlit as st
import pandas as pd
import plotly.express as px
import os
from datetime import date
from openpyxl import load_workbook

# -----------------------------
#         CONSTANTS
# -----------------------------
FILE_NAME = "VCR - All Enacted Law & Legislative Tracker.xlsx"
SHEET_NAME = "Enacted Federal Law (Ex. J.Res."

# -----------------------------
#        DATA LOADING
# -----------------------------
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

    # Use openpyxl to extract the actual hyperlink targets from the relevant column
    workbook = load_workbook(FILE_NAME)
    sheet = workbook[SHEET_NAME]
    links = []
    for row in sheet.iter_rows(
        min_row=2, max_row=sheet.max_row, min_col=4, max_col=4
    ):
        cell = row[0]
        links.append(cell.hyperlink.target if cell.hyperlink else None)

    df["Link"] = links

    # Extract plain text for "Title" by removing embedded URLs from the string
    # (assuming the URLs always start with http and continue until next space)
    df["Title"] = df["Title and Link"].str.replace(r"http[^\s]+", "", regex=True).str.strip()

    # Explode authors by comma to facilitate filtering
    # e.g., "Sen. A, Sen. B" -> two rows
    df = df.assign(Author=df["Authors"].str.split(",")).explode("Author")
    df["Author"] = df["Author"].str.strip()  # remove whitespace

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


# -----------------------------
#       HELPER FUNCTIONS
# -----------------------------
def generate_scatter_plot(
    data: pd.DataFrame,
    x_col: str,
    y_col: str,
    color_col: str,
    title: str,
    text_size: int = 12,
) -> px.scatter:
    """
    Generates a scatter plot with hover info and consistent styling.
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
            "Link": True,  # Display link in hover so user can copy/paste
            color_col: True
        },
        labels={
            "Policy Area": "Policy Area",
            "Date": "Date Introduced",
            "Author": "Author",
        },
        title=title,
    )
    fig.update_layout(
        autosize=True,
        height=700,
        font=dict(size=text_size),
        margin=dict(l=40, r=40, t=80, b=40),
    )
    return fig


def display_results_table(df: pd.DataFrame):
    """
    Displays a summary and a nicely formatted table of the results.
    """
    count = len(df)
    st.write(f"**Total matching records:** {count}")
    if count > 0:
        # We can show a simplified version of the data table, dropping
        # columns we don’t want repeated. Or you can keep them all.
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


# -----------------------------
#       MAIN APP
# -----------------------------
def main():
    st.set_page_config(page_title="Enacted Federal Legislation Tracker", layout="wide")
    st.title("Enacted Federal Legislation Tracker")

    # 1. Load Data
    data = get_filtered_data()
    if data.empty:
        st.error("No data available. Please ensure the file is available and correctly formatted.")
        return

    # 2. Introduction / Instructions
    st.markdown("""
    Welcome to the **Enacted Federal Legislation Tracker**! 

    - **Filter** records by *Author*, *Method of Enactment*, *Policy Area*, or *Date Range*.
    - **View** matching records in a table format.
    - **Visualize** data in an interactive scatter plot.
    - For **advanced visualization** options, click the **'Show Advanced Filters'** expander below.
    ---
    """)

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

    # Determine which filter widget to show based on the radio selection
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

    # Filter data
    # If a particular filter list is empty, we include all possibilities
    # If date_range is default, it includes entire range
    filtered_data = data[
        ((data["Author"].isin(author_filter)) | (len(author_filter) == 0)) &
        ((data["Policy Area"].isin(policy_filter)) | (len(policy_filter) == 0)) &
        ((data["Enactment Method"].isin(enactment_filter)) | (len(enactment_filter) == 0)) &
        (data["Date"] >= pd.to_datetime(date_range[0])) &
        (data["Date"] <= pd.to_datetime(date_range[1]))
    ]

    # 4. Display Results Table
    st.subheader("Filtered Results")
    display_results_table(filtered_data)

    # 5. Basic Scatter Plot
    if not filtered_data.empty:
        fig = generate_scatter_plot(
            data=filtered_data,
            x_col="Policy Area",
            y_col="Date",
            color_col="Author",
            title="Basic Visualization: Policy Area vs. Date (Colored by Author)",
            text_size=12,
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No data to visualize. Please adjust your filters above.")

    # 6. Optional Additional Visualization (e.g., a bar chart by year)
    with st.expander("Show Bar Chart by Year", expanded=False):
        # Add a 'Year' column for grouping
        temp_df = filtered_data.copy()
        temp_df["Year"] = temp_df["Date"].dt.year
        # Count number of bills per year
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

    # 7. Advanced Mode (Expander)
    with st.expander("Show Advanced Filters and Visualization", expanded=False):
        st.markdown("""
        **Advanced Mode** allows you to:
        - Apply multiple filters simultaneously.
        - Customize axes and color variables in the scatter plot.
        - Adjust font sizes.
        """)

        # Advanced Filters
        advanced_author_filter = st.multiselect(
            "Filter by Author",
            options=authors,
            default=author_filter  # carry over chosen filters
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

        # Additional styling control
        text_size = st.slider("Text Size in Chart", min_value=10, max_value=30, value=12, step=1)

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

        # Let user choose variables for scatter
        axis_options = ["Policy Area", "Date", "Author"]
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
            )
            st.plotly_chart(fig_advanced, use_container_width=True)
        else:
            st.info("No data for Advanced Visualization. Please update the filters above.")


# -----------------------------
#     ENTRY POINT
# -----------------------------
if __name__ == "__main__":
    main()

