import streamlit as st
import pandas as pd
import plotly.express as px
import os

from datetime import date

# Load data
FILE_NAME = "VCR - All Enacted Law & Legislative Tracker.xlsx"
SHEET_NAME = "Enacted Federal Law (Ex. J.Res."

def load_data():
    if not os.path.exists(FILE_NAME):
        st.error(f"File {FILE_NAME} not found in the current directory.")
        return None

    # Load the entire spreadsheet to ensure all rows are included
    df = pd.read_excel(FILE_NAME, sheet_name=SHEET_NAME, engine='openpyxl')

    # Clean and structure the data
    df = df[["Author(s)", "Original Introduction Date:", "Main policy topic", "Current Link (Inc. Amndt, if applicable)", "Method of Enactment"]]
    df.columns = ["Authors", "Date", "Policy Area", "Title and Link", "Enactment Method"]

    # Convert Date column to datetime explicitly
    df["Date"] = pd.to_datetime(df["Date"], errors='coerce')

    # Extract hyperlinks using openpyxl
    from openpyxl import load_workbook
    workbook = load_workbook(FILE_NAME)
    sheet = workbook[SHEET_NAME]

    links = []
    for row in sheet.iter_rows(min_row=2, max_row=sheet.max_row, min_col=4, max_col=4):
        cell = row[0]
        if cell.hyperlink:
            links.append(cell.hyperlink.target)
        else:
            links.append(None)

    df["Link"] = links

    # Extract plain titles
    df["Title"] = df["Title and Link"].str.replace(r'http[^\s]+', '', regex=True).str.strip()

    # Split authors into multiple rows for filtering
    df = df.assign(Author=df["Authors"].str.split(",")).explode("Author").reset_index(drop=True)

    return df

# Load data
@st.cache_data
def get_filtered_data():
    data = load_data()
    if data is not None:
        data = data.dropna(subset=["Date"]).reset_index(drop=True)
        return data
    return None

# Main function
def main():
    data = get_filtered_data()

    if data is None:
        st.error("No data available to display.")
        return

    st.title("Enacted Federal Legislation Tracker")

    # Initial selection screen
    search_option = st.radio(
        "How would you like to search for bills?",
        ["Author", "Method of Enactment", "Policy Area", "Date Range"],
        index=0
    )

    # Initialize default filters
    authors = data["Author"].unique()
    policy_areas = data["Policy Area"].unique()
    methods = data["Enactment Method"].unique()
    min_date = data["Date"].min().date()
    max_date = data["Date"].max().date()

    author_filter = []
    policy_filter = []
    enactment_filter = []
    date_range = (min_date, max_date)

    if search_option == "Author":
        author_filter = st.multiselect("Select Authors", options=authors, default=[])
    elif search_option == "Method of Enactment":
        enactment_filter = st.multiselect("Select Methods of Enactment", options=methods, default=[])
    elif search_option == "Policy Area":
        policy_filter = st.multiselect("Select Policy Areas", options=policy_areas, default=[])
    elif search_option == "Date Range":
        date_range = st.slider("Select Date Range", min_value=min_date, max_value=max_date, value=(min_date, max_date))

    # Apply filters only if at least one filter is active
    if any([author_filter, policy_filter, enactment_filter, date_range != (min_date, max_date)]):
        filtered_data = data[
            (data["Author"].isin(author_filter) if author_filter else True) &
            (data["Policy Area"].isin(policy_filter) if policy_filter else True) &
            (data["Enactment Method"].isin(enactment_filter) if enactment_filter else True) &
            (data["Date"] >= pd.to_datetime(date_range[0])) & (data["Date"] <= pd.to_datetime(date_range[1]))
        ]

        # Simple visualization in basic mode
        st.subheader("Filtered Results")
        st.write(filtered_data.drop(columns="Title and Link"))

        fig = px.scatter(
            filtered_data,
            x="Policy Area",
            y="Date",
            size=[10] * len(filtered_data),  # Fixed size for orbs
            color="Author",
            hover_name="Title",
            hover_data={"Date": True, "Link": False},
            labels={"Policy Area": "Policy Area", "Date": "Date Introduced"},
            title="Simple Visualization (Click full screen on top right of figure)",
        )

        # Add clickable functionality to orbs
        for i, row in filtered_data.iterrows():
            if pd.notna(row["Link"]):
                fig.add_annotation(
                    x=row["Policy Area"],
                    y=row["Date"],
                    text=f'<a href="{row["Link"]}" target="_blank">{row["Title"]}</a>',
                    showarrow=False,
                    font=dict(color="blue"),
                )

        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Please apply at least one filter to display the visualization.")

    # Advanced mode
    if st.button("Switch to Advanced Mode"):
        st.sidebar.header("Advanced Filters")

        advanced_author_filter = st.sidebar.multiselect("Filter by Author", options=authors, default=author_filter)
        advanced_policy_filter = st.sidebar.multiselect("Filter by Policy Area", options=policy_areas, default=policy_filter)
        advanced_enactment_filter = st.sidebar.multiselect("Filter by Enactment Method", options=methods, default=enactment_filter)
        advanced_date_range = st.sidebar.slider("Select Date Range", min_value=min_date, max_value=max_date, value=date_range)

        text_size = st.sidebar.slider("Text Size", min_value=10, max_value=30, value=12, step=1)

        advanced_filtered_data = data[
            (data["Author"].isin(advanced_author_filter)) &
            (data["Policy Area"].isin(advanced_policy_filter)) &
            (data["Enactment Method"].isin(advanced_enactment_filter)) &
            (data["Date"] >= pd.to_datetime(advanced_date_range[0])) & (data["Date"] <= pd.to_datetime(advanced_date_range[1]))
        ]

        # Visualization
        x_axis = st.sidebar.selectbox("X-Axis", ["Policy Area", "Date", "Author"], index=0)
        y_axis = st.sidebar.selectbox("Y-Axis", ["Policy Area", "Date", "Author"], index=1)
        color = st.sidebar.selectbox("Color", ["Policy Area", "Date", "Author"], index=2)

        st.title("Advanced Visualization")

        fig = px.scatter(
            advanced_filtered_data,
            x=x_axis,
            y=y_axis,
            size=[10] * len(advanced_filtered_data),
            color=color,
            hover_name="Title",
            hover_data={"Date": True, "Link": False},
            labels={"Policy Area": "Policy Area", "Date": "Date Introduced"},
            title="Advanced Visualization",
        )

        fig.update_layout(
            autosize=True,
            height=800,
            font=dict(size=text_size),
        )

        st.plotly_chart(fig, use_container_width=True)

if __name__ == "__main__":
    main()

