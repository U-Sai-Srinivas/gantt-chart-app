import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
from datetime import date

# Page configuration
st.set_page_config(page_title="Dynamic Gantt Chart", layout="wide")
st.title("📊 Dynamic Gantt Chart Generator")

# --- SIDEBAR: Project Management & Styling ---
with st.sidebar:
    st.header("📂 Manage Projects")
    
    st.subheader("Open Project")
    uploaded_file = st.file_uploader("Upload a saved .csv file", type=["csv"])
    
    if uploaded_file is not None:
        try:
            df = pd.read_csv(uploaded_file)
            if 'Start Date' in df.columns:
                df['Start Date'] = pd.to_datetime(df['Start Date'], errors='coerce')
            if 'End Date' in df.columns:
                df['End Date'] = pd.to_datetime(df['End Date'], errors='coerce')
            st.session_state.task_data = df
            st.success("Project loaded successfully!")
        except Exception as e:
            st.error(f"Error loading file: {e}")
            
    st.divider()
    
    st.subheader("Save Project")
    # Button is injected lower in the code to access edited_df
    
    st.subheader("Templates")
    template_df = pd.DataFrame(columns=["Task ID", "Task Name", "Type", "Resource", "Start Date", "End Date", "Duration (Days)", "Dependencies"])
    template_csv = template_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📄 Download CSV Template",
        data=template_csv,
        file_name="gantt_template.csv",
        mime="text/csv",
        use_container_width=True,
        key="template_dl_btn"
    )

    st.divider()
    
    # NEW FEATURE: Dependency Styling Controls
    st.header("🎨 Chart Styling")
    conn_color = st.color_picker("Connector Color", "#888888")
    conn_width = st.slider("Connector Thickness", 1, 5, 2)
    conn_style = st.selectbox("Connector Style", ["dot", "dash", "solid"])

# 1. Data Initialization
if 'task_data' not in st.session_state:
    st.session_state.task_data = pd.DataFrame({
        "Task ID": ["T1", "T2", "M1", "T3", "T4", "G1"],
        "Task Name": ["Project Scoping", "Design Phase", "Design Approval", "Backend Dev", "Frontend Dev", "Launch Decision"],
        "Type": ["Task", "Task", "Milestone", "Task", "Task", "Go/No-Go"],
        "Resource": ["Alice", "Bob", "Client", "Charlie", "Alice", "Stakeholders"],
        "Start Date": [date.today(), pd.NaT, pd.NaT, pd.NaT, pd.NaT, pd.NaT], 
        "End Date": [pd.NaT, pd.NaT, pd.NaT, pd.NaT, pd.NaT, pd.NaT], 
        "Duration (Days)": [3, 5, 0, 7, 6, 0], 
        "Dependencies": ["", "T1", "T2", "M1", "M1", "T3, T4"]
    })

# --- NEW SAFEGUARD: Make old CSVs backwards compatible ---
# If an older project is loaded, ensure it gets the new columns to prevent KeyErrors
if 'End Date' not in st.session_state.task_data.columns:
    st.session_state.task_data['End Date'] = pd.NaT
if 'Type' not in st.session_state.task_data.columns:
    st.session_state.task_data['Type'] = 'Task'
# ---------------------------------------------------------

# Force datetime to prevent type compatibility crashes
st.session_state.task_data['Start Date'] = pd.to_datetime(st.session_state.task_data['Start Date'], errors='coerce')
st.session_state.task_data['End Date'] = pd.to_datetime(st.session_state.task_data['End Date'], errors='coerce')

# 2. Editable Grid UI
st.subheader("1. Edit Your Tasks")
col1, col2, col3 = st.columns([2, 1, 1])

with col1:
    st.markdown("Modify dates, durations, or dependencies. **Enter End Date OR Duration.**")
with col2:
    project_start = st.date_input("Global Project Start", date.today())
with col3:
    # NEW FEATURE: Timeline Resolution and Theme
    timeline_view = st.selectbox("Timeline View", ["Auto", "Weeks", "Months", "Quarters"])
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
        "Type": st.column_config.SelectboxColumn("Type", options=["Task", "Milestone", "Go/No-Go"], required=True),
        "Resource": st.column_config.TextColumn(),
        "Start Date": st.column_config.DateColumn("Start Date"), 
        "End Date": st.column_config.DateColumn("End Date"), # NEW
        "Duration (Days)": st.column_config.NumberColumn("Duration", min_value=0),
        "Dependencies": st.column_config.TextColumn()
    }
)

with st.sidebar:
    csv_data = edited_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="⬇️ Download Active Project",
        data=csv_data,
        file_name="my_gantt_project.csv",
        mime="text/csv",
        use_container_width=True,
        key="active_dl_btn"
    )

# 3. Calculation Logic (Now Bi-Directional)
def calculate_gantt_dates(df, project_start_date):
    df = df.dropna(subset=['Task ID']).copy()
    df['Dependencies'] = df['Dependencies'].fillna("").astype(str)
    
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
            deps_str = task['Dependencies']
            
            manual_start = task.get('Start Date')
            manual_end = task.get('End Date')
            manual_dur = task.get('Duration (Days)')
            
            deps = [d.strip() for d in deps_str.split(',')] if deps_str.strip() else []
            
            if not deps or all(d in task_dict for d in deps if d):
                # Determine Start Date
                if not deps or not any(d for d in deps):
                    if pd.notna(manual_start) and manual_start != "":
                        start_date = pd.to_datetime(manual_start).date()
                    else:
                        start_date = valid_project_start
                else:
                    valid_deps = [d for d in deps if d in task_dict]
                    if valid_deps:
                        start_date = max(task_dict[d]['end_date'] for d in valid_deps)
                    else:
                        start_date = valid_project_start
                
                start_np = np.datetime64(start_date)
                start_date = pd.to_datetime(np.busday_offset(start_np, 0, roll='forward')).date()
                start_np_calc = np.datetime64(start_date)
                        
                # NEW LOGIC: Determine End Date and Duration (Bi-Directional)
                if pd.notna(manual_end) and manual_end != "":
                    # User provided an End Date: Calculate the Duration backwards
                    end_date = pd.to_datetime(manual_end).date()
                    end_np = np.datetime64(end_date)
                    calculated_dur = np.busday_count(start_np_calc, end_np)
                    duration = max(0, int(calculated_dur)) 
                else:
                    # User provided a Duration (or blank): Calculate the End Date forwards
                    duration = int(manual_dur) if pd.notna(manual_dur) else 1
                    end_date = pd.to_datetime(np.busday_offset(start_np_calc, duration)).date()
                
                task_dict[task_id] = {
                    'start_date': start_date,
                    'end_date': end_date,
                    'duration': duration
                }
                progress_made = True
            else:
                remaining_tasks.append(task)
        
        pending_tasks = remaining_tasks

    # Map calculated results back to dataframe
    df['Start Date'] = df['Task ID'].astype(str).str.strip().map(lambda x: task_dict.get(x, {}).get('start_date', pd.NaT))
    df['End Date'] = df['Task ID'].astype(str).str.strip().map(lambda x: task_dict.get(x, {}).get('end_date', pd.NaT))
    df['Duration (Days)'] = df['Task ID'].astype(str).str.strip().map(lambda x: task_dict.get(x, {}).get('duration', 1))
    
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
        color="Resource",
        hover_data=["Task ID", "Type", "Duration (Days)", "Dependencies"],
        template=plotly_template 
    )
    
    fig.update_yaxes(autorange="reversed") 
    
    # NEW LOGIC: Customizable Dependency Lines
    for index, row in valid_df.iterrows():
        if pd.notna(row['Dependencies']) and str(row['Dependencies']).strip() != "":
            deps = [d.strip() for d in str(row['Dependencies']).split(',')]
            for d in deps:
                dep_row = valid_df[valid_df['Task ID'] == d]
                if not dep_row.empty:
                    dep_row = dep_row.iloc[0]
                    fig.add_trace(go.Scatter(
                        x=[dep_row['End Date'], row['Start Date']],
                        y=[dep_row['Task Name'], row['Task Name']],
                        mode='lines+markers',
                        line=dict(shape='hv', color=conn_color, width=conn_width, dash=conn_style),
                        marker=dict(symbol='circle', size=[0, 6], color=conn_color), 
                        showlegend=False,
                        hoverinfo='skip'
                    ))
        
        # Milestones / Go-NoGo
        if row.get('Type') == 'Milestone':
            fig.add_trace(go.Scatter(
                x=[row['End Date']], y=[row['Task Name']],
                mode='markers', marker=dict(symbol='star', size=20, color='gold', line=dict(width=1, color='black')),
                showlegend=False, hoverinfo='skip'
            ))
        elif row.get('Type') == 'Go/No-Go':
            fig.add_trace(go.Scatter(
                x=[row['End Date']], y=[row['Task Name']],
                mode='markers', marker=dict(symbol='diamond', size=18, color='crimson', line=dict(width=1, color='black')),
                showlegend=False, hoverinfo='skip'
            ))

    # NEW LOGIC: Dynamic X-Axis Formatting
    if timeline_view == "Months":
        fig.update_xaxes(dtick="M1", tickformat="%b %Y")
    elif timeline_view == "Quarters":
        fig.update_xaxes(dtick="M3", tickformat="Q%q %Y")
    elif timeline_view == "Weeks":
        fig.update_xaxes(dtick=604800000, tickformat="%W %Y") # 7 days in milliseconds

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
