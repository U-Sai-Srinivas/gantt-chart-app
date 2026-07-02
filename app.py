import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
from datetime import date

# Page configuration
st.set_page_config(page_title="Dynamic Gantt Chart", layout="wide")
st.title("📊 Dynamic Gantt Chart Generator")

# 1. Dummy Data Initialization
if 'task_data' not in st.session_state:
    st.session_state.task_data = pd.DataFrame({
        "Task ID": ["T1", "T2", "T3", "T4", "T5"],
        "Task Name": ["Project Scoping", "Design Phase", "Backend Dev", "Frontend Dev", "Integration Testing"],
        "Resource": ["Alice", "Bob", "Charlie", "Alice", "Team"],
        "Duration (Days)": [3, 5, 7, 6, 4],
        "Dependencies": ["", "T1", "T2", "T2", "T3, T4"]
    })

# 2. Editable Grid UI
st.subheader("1. Edit Your Tasks")
col1, col2 = st.columns([3, 1])

with col1:
    st.markdown("Modify durations, names, resources, or dependencies (comma-separated). Add or delete rows as needed. *Note: Durations are calculated in business days.*")
with col2:
    project_start = st.date_input("Project Start Date", date.today())

edited_df = st.data_editor(
    st.session_state.task_data,
    num_rows="dynamic",
    use_container_width=True,
    hide_index=True,
    key="editor_state",
    column_config={
        "Task ID": st.column_config.TextColumn(required=True),
        "Task Name": st.column_config.TextColumn(required=True),
        "Resource": st.column_config.TextColumn(),
        "Duration (Days)": st.column_config.NumberColumn(required=True, min_value=1),
        "Dependencies": st.column_config.TextColumn()
    }
)

# 3. Calculation Logic (Now with Business Days)
def calculate_gantt_dates(df, project_start_date):
    df = df.dropna(subset=['Task ID', 'Duration (Days)']).copy()
    df['Duration (Days)'] = pd.to_numeric(df['Duration (Days)'], errors='coerce').fillna(1).astype(int)
    df['Dependencies'] = df['Dependencies'].fillna("").astype(str)

    task_dict = {}
    pending_tasks = df.to_dict('records')
    
    # Snap project start date to the nearest business day (rolls forward if weekend)
    project_start_np = np.datetime64(project_start_date)
    valid_project_start = pd.to_datetime(np.busday_offset(project_start_np, 0, roll='forward')).date()

    progress_made = True
    while pending_tasks and progress_made:
        progress_made = False
        remaining_tasks = []
        
        for task in pending_tasks:
            task_id = str(task['Task ID']).strip()
            duration = task['Duration (Days)']
            deps_str = task['Dependencies']
            
            deps = [d.strip() for d in deps_str.split(',')] if deps_str.strip() else []
            
            if not deps or all(d in task_dict for d in deps if d):
                if not deps or not any(d for d in deps):
                    start_date = valid_project_start
                else:
                    valid_deps = [d for d in deps if d in task_dict]
                    if valid_deps:
                        # Task starts on the LATEST end date of all its dependencies
                        proposed_start = max(task_dict[d]['end_date'] for d in valid_deps)
                        # Ensure the start date is a business day
                        proposed_start_np = np.datetime64(proposed_start)
                        start_date = pd.to_datetime(np.busday_offset(proposed_start_np, 0, roll='forward')).date()
                    else:
                        start_date = valid_project_start
                        
                # Calculate end date strictly using business days
                start_np = np.datetime64(start_date)
                end_date = pd.to_datetime(np.busday_offset(start_np, duration)).date()
                
                task_dict[task_id] = {
                    'start_date': start_date,
                    'end_date': end_date
                }
                progress_made = True
            else:
                remaining_tasks.append(task)
        
        pending_tasks = remaining_tasks

    df['Start Date'] = df['Task ID'].astype(str).str.strip().map(lambda x: task_dict.get(x, {}).get('start_date', pd.NaT))
    df['End Date'] = df['Task ID'].astype(str).str.strip().map(lambda x: task_dict.get(x, {}).get('end_date', pd.NaT))
    
    return df

calculated_df = calculate_gantt_dates(edited_df, project_start)
valid_df = calculated_df.dropna(subset=['Start Date', 'End Date'])

# 4. Visualization
st.subheader("2. Project Timeline")

if len(valid_df) < len(calculated_df):
    st.error("⚠️ Some tasks could not be scheduled. Please check your data for circular dependencies (e.g., Task A depends on Task B, and Task B depends on Task A) or invalid Task IDs.")

if not valid_df.empty:
    fig = px.timeline(
        valid_df,
        x_start="Start Date",
        x_end="End Date",
        y="Task Name",
        text="Task Name",
        color="Resource",
        hover_data=["Task ID", "Duration (Days)", "Dependencies"]
    )
    
    fig.update_yaxes(autorange="reversed") 
    fig.update_layout(
        xaxis_title="Timeline",
        yaxis_title="",
        height=max(400, len(valid_df) * 40), 
        margin=dict(l=20, r=20, t=40, b=20),
        showlegend=True
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Add tasks and valid durations to generate the timeline.")