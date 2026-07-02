import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
from datetime import date

# Page configuration
st.set_page_config(page_title="Dynamic Gantt Chart", layout="wide")
st.title("📊 Dynamic Gantt Chart Generator")

# --- SIDEBAR: Project Management ---
# --- SIDEBAR: Project Management ---
with st.sidebar:
    st.header("📂 Manage Projects")
    
    # 1. Load an existing project
    st.subheader("Open Project")
    uploaded_file = st.file_uploader("Upload a saved .csv file", type=["csv"])
    
    if uploaded_file is not None:
        try:
            st.session_state.task_data = pd.read_csv(uploaded_file)
            st.success("Project loaded successfully!")
        except Exception as e:
            st.error(f"Error loading file: {e}")
            
    st.divider()
    
    # 2. Save current project
    st.subheader("Save Project")
    if 'editor_state' in st.session_state and st.session_state.editor_state is not None:
        pass 
        
    # 3. Download Blank Template
    st.subheader("Templates")
    st.markdown("Download an empty template to start a new project offline.")
    template_df = pd.DataFrame(columns=["Task ID", "Task Name", "Type", "Resource", "Start Date", "Duration (Days)", "Dependencies"])
    template_csv = template_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📄 Download CSV Template",
        data=template_csv,
        file_name="gantt_template.csv",
        mime="text/csv",
        use_container_width=True
    )
    # 2. Save current project
    st.subheader("Save Project")
    if 'editor_state' in st.session_state and st.session_state.editor_state is not None:
        # We need to grab the current state from the data editor to save it
        pass # The download button will use edited_df below
        
    # 3. Download Blank Template
    st.subheader("Templates")
    st.markdown("Download an empty template to start a new project offline.")
    template_df = pd.DataFrame(columns=["Task ID", "Task Name", "Type", "Resource", "Start Date", "Duration (Days)", "Dependencies"])
    template_csv = template_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📄 Download CSV Template",
        data=template_csv,
        file_name="gantt_template.csv",
        mime="text/csv",
        use_container_width=True
    )


# 1. Data Initialization
if 'task_data' not in st.session_state:
    st.session_state.task_data = pd.DataFrame({
        "Task ID": ["T1", "T2", "M1", "T3", "T4", "G1"],
        "Task Name": ["Project Scoping", "Design Phase", "Design Approval", "Backend Dev", "Frontend Dev", "Launch Decision"],
        "Type": ["Task", "Task", "Milestone", "Task", "Task", "Go/No-Go"],
        "Resource": ["Alice", "Bob", "Client", "Charlie", "Alice", "Stakeholders"],
        # Change 1: Use pd.NaT instead of None for missing dates
        "Start Date": [date.today(), pd.NaT, pd.NaT, pd.NaT, pd.NaT, pd.NaT], 
        "Duration (Days)": [3, 5, 0, 7, 6, 0], 
        "Dependencies": ["", "T1", "T2", "M1", "M1", "T3, T4"]
    })

# --- CRITICAL FIX ---
# Force pandas to treat this column strictly as datetimes. 
# This prevents crashes when loading the blank CSV template!
st.session_state.task_data['Start Date'] = pd.to_datetime(st.session_state.task_data['Start Date'], errors='coerce')
# --------------------
# 2. Editable Grid UI
st.subheader("1. Edit Your Tasks")
col1, col2 = st.columns([3, 1])

with col1:
    st.markdown("Modify dates, durations, or dependencies. Use **0 duration** for Milestones.")
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
        "Type": st.column_config.SelectboxColumn(
            "Type", 
            options=["Task", "Milestone", "Go/No-Go"], 
            required=True
        ),
        "Resource": st.column_config.TextColumn(),
        "Start Date": st.column_config.DateColumn("Start Date (Optional)"), 
        "Duration (Days)": st.column_config.NumberColumn(required=True, min_value=0), # Lowered to 0
        "Dependencies": st.column_config.TextColumn()
    }
)

# Put the save button here so it has access to edited_df
with st.sidebar:
    csv_data = edited_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="⬇️ Download Active Project",
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
    
    # Ensure Type column exists for older CSVs
    if 'Type' not in df.columns:
        df['Type'] = 'Task'

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
                        
                # Calculate end date using business days (0 duration stays on the same day)
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
    # Set the Plotly template
    plotly_template = "plotly_dark" if theme_choice == "Dark" else "plotly_white"

    fig = px.timeline(
        valid_df,
        x_start="Start Date",
        x_end="End Date",
        y="Task Name",
        text="Task Name",
        color="Resource",
        hover_data=["Task ID", "Type", "Duration (Days)", "Dependencies"],
        template=plotly_template 
    )
    
    fig.update_yaxes(autorange="reversed") 
    
    # ---------------------------------------------------------
    # DEPENDENCY ARROWS & MILESTONE ICONS
    # ---------------------------------------------------------
    arrow_color = "rgba(255,255,255,0.6)" if theme_choice == "Dark" else "rgba(0,0,0,0.4)"
    
    for index, row in valid_df.iterrows():
        # Draw dependency arrows
        if pd.notna(row['Dependencies']) and str(row['Dependencies']).strip() != "":
            deps = [d.strip() for d in str(row['Dependencies']).split(',')]
            for d in deps:
                dep_row = valid_df[valid_df['Task ID'] == d]
                if not dep_row.empty:
                    dep_row = dep_row.iloc[0]
                    fig.add_annotation(
                        x=row['Start Date'], y=row['Task Name'],
                        ax=dep_row['End Date'], ay=dep_row['Task Name'],
                        xref="x", yref="y", axref="x", ayref="y",
                        showarrow=True, arrowhead=2, arrowsize=1,
                        arrowwidth=1.5, arrowcolor=arrow_color
                    )
        
        # Add special marker shapes for Milestones and Go/No-Go
        if row.get('Type') == 'Milestone':
            fig.add_trace(go.Scatter(
                x=[row['Start Date']], y=[row['Task Name']],
                mode='markers', marker=dict(symbol='star', size=20, color='gold', line=dict(width=1, color='black')),
                showlegend=False, hoverinfo='skip'
            ))
        elif row.get('Type') == 'Go/No-Go':
            fig.add_trace(go.Scatter(
                x=[row['Start Date']], y=[row['Task Name']],
                mode='markers', marker=dict(symbol='diamond', size=18, color='crimson', line=dict(width=1, color='black')),
                showlegend=False, hoverinfo='skip'
            ))

    # BRUTE FORCE THEME FIX: Override Streamlit's transparent backgrounds
    bg_color = "#111111" if theme_choice == "Dark" else "#FFFFFF"
    text_color = "#FFFFFF" if theme_choice == "Dark" else "#000000"

    fig.update_layout(
        xaxis_title="Timeline",
        yaxis_title="",
        height=max(400, len(valid_df) * 45), 
        margin=dict(l=20, r=20, t=40, b=20),
        showlegend=True,
        paper_bgcolor=bg_color,
        plot_bgcolor=bg_color,
        font=dict(color=text_color)
    )
    
    st.plotly_chart(fig, use_container_width=True, theme=None)
else:
    st.info("Add tasks and valid durations to generate the timeline.")
