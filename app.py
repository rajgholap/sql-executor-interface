import os
import json
import mysql.connector
import streamlit as st
from collections import Counter

# Sample JSON structure for config file
sample_config_json = {
    "environments": [
        {
            "name": "prod",
            "host": "prod_host",
            "user": "prod_user",
            "password": "prod_password"
        },
        {
            "name": "dev",
            "host": "dev_host",
            "user": "dev_user",
            "password": "dev_password"
        }
    ]
}

# Initialize session state for the toggle button
if "show_sample" not in st.session_state:
    st.session_state.show_sample = False

# Streamlit UI title
st.title("SQL Executor Interface")

# Toggle button to show/hide sample JSON format for config
if st.button("Show config.json format example"):
    st.session_state.show_sample = not st.session_state.show_sample  # Toggle state

# Display sample JSON when the button is active
if st.session_state.show_sample:
    st.json(sample_config_json)

# File uploader for environment configuration
config_file = st.file_uploader("Upload Environment Configuration File (config.json)", type=["json"])

# Initialize environment options from uploaded config file
env_options = {}
if config_file is not None:
    try:
        config_data = json.load(config_file)
        env_options = {f"{env['name']} ({env['host']})": env for env in config_data.get("environments", [])}
    except json.JSONDecodeError:
        st.error("Invalid JSON format. Please check your config file.")

# Function to execute SQL on a selected database
def execute_sql_file(file_path, database, env_config):
    connection = mysql.connector.connect(
        host=env_config["host"],
        user=env_config["user"],
        password=env_config["password"],
        database=database
    )
    cursor = connection.cursor()
    with open(file_path, 'r') as sql_file:
        sql_commands = sql_file.read().split(';')
    try:
        for command in sql_commands:
            if command.strip():
                cursor.execute(command)
        connection.commit()
        return None
    except mysql.connector.Error as err:
        connection.rollback()
        return f"Error on {database}: {err}"  # Return error message
    finally:
        cursor.close()
        connection.close()

# Display environment selection dropdown if env_options are loaded
if env_options:
    # Environment selection
    env_choice = st.selectbox("Select Environment:", list(env_options.keys()))
    env_config = env_options.get(env_choice)

    # Function to get databases based on selected environment, excluding system databases
    def get_databases(env_config):
        connection = mysql.connector.connect(
            host=env_config["host"],
            user=env_config["user"],
            password=env_config["password"]
        )
        cursor = connection.cursor()
        try:
            cursor.execute("SHOW DATABASES;")
            # Exclude default system databases
            system_databases = {'information_schema', 'sys', 'performance_schema', 'mysql'}
            return [db[0] for db in cursor.fetchall() if db[0] not in system_databases]
        except mysql.connector.Error as err:
            st.error(f"Error retrieving databases: {err}")
            return []
        finally:
            cursor.close()
            connection.close()

    # Function to determine pattern options based on database names
    def generate_patterns(databases):
        if not databases:
            return []
        prefix_counter = Counter(db.split('_')[0] for db in databases if '_' in db)
        
        # Check if each database name should be used fully or by prefix
        patterns = []
        for db in databases:
            if '_' in db:
                prefix = db.split('_')[0]
                # Use prefix if there are multiple databases with the same prefix
                if prefix_counter[prefix] > 1:
                    patterns.append(prefix)
                else:
                    # Use full name for unique database name
                    patterns.append(db)
            else:
                # Use full name if there's no underscore
                patterns.append(db)
        return list(set(patterns))  # Remove duplicates

    # Retrieve databases and generate patterns based on selected environment
    databases = get_databases(env_config)
    patterns = generate_patterns(databases)

    # Pattern selection based on databases in the environment
    if patterns:
        pattern = st.selectbox("Select Database Pattern:", patterns)
    else:
        st.warning("No databases found for the selected environment.")
        pattern = None

    # File uploader for SQL file
    uploaded_file = st.file_uploader("Upload SQL File", type=["sql"])

    # Define the execute button
    if st.button("Execute"):
        if uploaded_file is not None and env_config:
            # Save uploaded file
            file_path = os.path.join("uploads", uploaded_file.name)
            os.makedirs("uploads", exist_ok=True)
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getbuffer())

            # Check if pattern matches more than one database
            matching_databases = [db for db in databases if db.startswith(pattern)]
            # print('matching_databases : ', matching_databases)

            # Logic to select exact match or multiple prefixed databases
            if pattern in databases and len(matching_databases) == 1:
                # Select only the exact match if pattern is a standalone database
                selected_databases = [pattern]
            else:
                # Include all prefixed databases if no standalone exact match
                selected_databases = matching_databases
            # print('selected_databases : ',selected_databases)
            error_messages = []

            # Execute SQL file on each matching database
            for db in selected_databases:
                error = execute_sql_file(file_path, db, env_config)
                if error:
                    error_messages.append(error)

            # Display results at the bottom
            st.write("### Execution Results:")
            if error_messages:
                for message in error_messages:
                    st.error(message)
            else:
                st.success("SQL file executed successfully on all matching databases.")

            # Clean up uploaded file
            os.remove(file_path)
        elif uploaded_file is None:
            st.warning("Please upload a SQL file to execute.")
        elif not env_config:
            st.warning("Environment configuration is missing.")
else:
    st.warning("Please upload a valid environment configuration file.")


st.markdown("---")
st.markdown(
    "<p style='text-align: center; font-size: small;'>Developed by 👨‍💻 <b>Raj Gholap</b></p>",
    unsafe_allow_html=True
)