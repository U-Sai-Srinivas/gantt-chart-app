import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
from datetime import date

# Page configuration
st.set_page_config(page_title="Dynamic Gantt Chart", layout="wide")
st.title("📊 Dynamic Gantt Chart Generator")

# --- NEW SIDEBAR: Project Management ---
with st.sidebar:
    st.header("📂 Manage Projects")
    
    # 1. Load an existing project
    st.subheader("Open Project")
    uploaded_file = st.file_uploader("Upload a saved .csv file", type=["csv"])
    
    if uploaded_file is not None:
        try:
            # Read the uploaded CSV and overwrite the session state
            st.session_state.task_data = pd.read_csv(uploaded_file)
            st.success("Project loaded successfully!")
        except Exception as e:
            st.error(f"Error loading file: {e}")

# 1. Data Initialization (Uses uploaded data, or falls back to Dummy Data)
if 'task_data' not in st.session_state:
    st.session_state.task_data = pd.DataFrame({
        "Task ID": ["T1", "T2", "T3", "T4", "T5", "T6"],
        "Task Name": ["Project Scoping", "Design Phase", "Backend Dev", "Frontend Dev", "Integration Testing", "Independent Task"],
        "Resource": ["Alice", "Bob", "Charlie", "Alice", "Team", "Dave"],
        "Start Date": [date.today(), None, None, None, None, date.today()],
        "Duration (Days)": [3, 5, 7, 6, 4, 2],
        "Dependencies": ["", "T1", "T2", "T2", "T3, T4", ""]
    })

# --- END OF UPDATED SECTION ---

# 2. Editable Grid UI
st.subheader("1. Edit Your Tasks")
col1, col2 = st.columns([3, 1])

with col1:
    st.markdown("Modify dates, durations, or dependencies. *Tasks with dependencies will automatically calculate their start date, overriding manual inputs. Durations use business days.*")
with col2:
    project_start = st.date_input("Global Project Start", date.today())
    theme_choice = st.radio("Chart Theme", ["Light", "Dark"], horizontal=True)

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
        "Start Date": st.column_config.DateColumn("Start Date (Optional)"), 
        "Duration (Days)": st.column_config.NumberColumn(required=True, min_value=1),
        "Dependencies": st.column_config.TextColumn()
    }
)
# --- NEW: Save Project Button ---
with st.sidebar:
    st.divider()
    st.subheader("Save Project")
    st.markdown("Download your current tasks to save your progress.")
    
    # Convert the edited dataframe to a CSV format
    csv_data = edited_df.to_csv(index=False).encode('utf-8')
    
    st.download_button(
        label="⬇️ Download Project File",
        data=csv_data,
        file_name="my_gantt_project.csv",
        mime="text/csv",
        use_container_width=True
    )

# 3. Calculation Logic 
def calculate_gantt_dates(df, project_start_date):
    df = df.dropna(subset=['Task ID', 'Duration (Days)']).copy()
    df['Duration (Days)'] = pd.to_numeric(df['Duration (Days)'], errors='coerce').fillna(1).astype(int)
    df['Dependencies'] = df['Dependencies'].fillna("").astype(str)

    task_dict = {}
    pending_tasks = df.to_dict('records')
    
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
            manual_start = task.get('Start Date') 
            
            deps = [d.strip() for d in deps_str.split(',')] if deps_str.strip() else []
            
            if not deps or all(d in task_dict for d in deps if d):
                if not deps or not any(d for d in deps):
                    if pd.notna(manual_start) and manual_start != "":
                        start_date = pd.to_datetime(manual_start).date()
                    else:
                        start_date = valid_project_start
                else:
                    valid_deps = [d for d in deps if d in task_dict]
                    if valid_deps:
                        proposed_start = max(task_dict[d]['end_date'] for d in valid_deps)
                        start_date = proposed_start
                    else:
                        start_date = valid_project_start
                
                # Snap start date to nearest business day
                start_np = np.datetime64(start_date)
                start_date = pd.to_datetime(np.busday_offset(start_np, 0, roll='forward')).date()
                        
                # Calculate end date using business days
                start_np_calc = np.datetime64(start_date)
                end_date = pd.to_datetime(np.busday_offset(start_np_calc, duration)).date()
                
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
    st.error("⚠️ Some tasks could not be scheduled. Check for circular dependencies or invalid Task IDs.")

if not valid_df.empty:
    plotly_template = "plotly_dark" if theme_choice == "Dark" else "plotly_white"

    fig = px.timeline(
        valid_df,
        x_start="Start Date",
        x_end="End Date",
        y="Task Name",
        text="Task Name",
        color="Resource",
        hover_data=["Task ID", "Duration (Days)", "Dependencies"],
        template=plotly_template 
    )
    
    fig.update_yaxes(autorange="reversed") 
    
    # ---------------------------------------------------------
    # NEW LOGIC: Manually draw dependency arrows between tasks
    # ---------------------------------------------------------
    arrow_color = "rgba(255,255,255,0.6)" if theme_choice == "Dark" else "rgba(0,0,0,0.4)"
    
    for index, row in valid_df.iterrows():
        if pd.notna(row['Dependencies']) and str(row['Dependencies']).strip() != "":
            deps = [d.strip() for d in str(row['Dependencies']).split(',')]
            for d in deps:
                dep_row = valid_df[valid_df['Task ID'] == d]
                if not dep_row.empty:
                    dep_row = dep_row.iloc[0]
                    
                    # Draw arrow from Dependency End Date to Current Task Start Date
                    fig.add_annotation(
                        x=row['Start Date'],
                        y=row['Task Name'],
                        ax=dep_row['End Date'],
                        ay=dep_row['Task Name'],
                        xref="x", yref="y",
                        axref="x", ayref="y",
                        showarrow=True,
                        arrowhead=2,
                        arrowsize=1,
                        arrowwidth=1.5,
                        arrowcolor=arrow_color
                    )

    fig.update_layout(
        xaxis_title="Timeline",
        yaxis_title="",
        height=max(400, len(valid_df) * 40), 
        margin=dict(l=20, r=20, t=40, b=20),
        showlegend=True
    )
    
    # NEW LOGIC: Force theme=None so Streamlit respects the Light/Dark templates
    st.plotly_chart(fig, use_container_width=True, theme=None)
else:
    st.info("Add tasks and valid durations to generate the timeline.")
