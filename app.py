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
    df = df[[
        "Author(s)",
        "Original Introduction Date:",
        "Main policy topic",
        "Current Link (Inc. Amndt, if applicable)",
        "Method of Enactment",
    ]]
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
        # Ensure no rows are dropped prematurely
        data = data.dropna(subset=["Date"]).reset_index(drop=True)
        return data
    return None

# Main function
def main():
    data = get_filtered_data()

    if data is not None:
        # Sidebar filters
        st.sidebar.header("Filters")

        # Buttons to select/deselect all authors and policy areas
        if st.sidebar.button("Select All Authors"):
            selected_authors = list(data["Author"].unique())
        elif st.sidebar.button("Deselect All Authors"):
            selected_authors = []
        else:
            selected_authors = ["Kyuoku Chan", "Norman Nord"]

        if st.sidebar.button("Select All Policy Areas"):
            selected_policies = list(data["Policy Area"].unique())
        elif st.sidebar.button("Deselect All Policy Areas"):
            selected_policies = []
        else:
            selected_policies = data["Policy Area"].unique()

        # Date range slider with all available dates
        min_date = data["Date"].min().date()
        max_date = data["Date"].max().date()

        if pd.isnull(min_date) or pd.isnull(max_date):
            st.error("No valid dates available in the data.")
            return

        # Set default date range to include the entire range
        date_range = st.sidebar.slider("Select Date Range", min_value=min_date, max_value=max_date, value=(min_date, max_date))

        author_filter = st.sidebar.multiselect("Filter by Author", options=data["Author"].unique(), default=selected_authors)
        policy_filter = st.sidebar.multiselect("Filter by Policy Area", options=data["Policy Area"].unique(), default=selected_policies)
        enactment_filter = st.sidebar.multiselect("Filter by Enactment Method", options=data["Enactment Method"].unique(), default=data["Enactment Method"].unique())

        x_axis = st.sidebar.selectbox("X-Axis", ["Policy Area", "Date", "Author"], index=0)
        y_axis = st.sidebar.selectbox("Y-Axis", ["Policy Area", "Date", "Author"], index=1)
        color = st.sidebar.selectbox("Color", ["Policy Area", "Date", "Author"], index=2)

        # Add sliders for orb and text size
        orb_size = st.sidebar.slider("Orb Size", min_value=5, max_value=50, value=10, step=1)
        text_size = st.sidebar.slider("Text Size", min_value=10, max_value=30, value=12, step=1)

        # Apply filters
        filtered_data = data[
            (data["Author"].isin(author_filter)) &
            (data["Policy Area"].isin(policy_filter)) &
            (data["Enactment Method"].isin(enactment_filter)) &
            (data["Date"] >= pd.to_datetime(date_range[0])) & (data["Date"] <= pd.to_datetime(date_range[1]))
        ]

        # Visualization
        st.title("Enacted Federal Legislation Tracker")

        # Create interactive scatter plot with full-screen default
        fig = px.scatter(
            filtered_data,
            x=x_axis,
            y=y_axis,
            size=[orb_size] * len(filtered_data),
            color=color,
            hover_name="Title",
            hover_data={"Date": True, "Link": False},
            labels={"Policy Area": "Policy Area", "Date": "Date Introduced"},
            title="Federal Legislation by Policy Area",
        )

        fig.update_layout(
            autosize=True,
            height=800,
            font=dict(size=text_size),  # Adjust text size
        )

        # Add clickable functionality
        for i, row in filtered_data.iterrows():
            if pd.notna(row["Link"]):
                fig.add_annotation(
                    x=row[x_axis],
                    y=row[y_axis],
                    text=f'<a href="{row["Link"]}" target="_blank">{row["Title"]}</a>',
                    showarrow=False,
                    font=dict(color="blue", size=text_size),
                )

        st.plotly_chart(fig, use_container_width=True)

        # Display filtered data
        st.subheader("Filtered Legislation")
        st.write(filtered_data.drop(columns="Title and Link"))
    else:
        st.error("No data available to display.")

if __name__ == "__main__":
    main()
