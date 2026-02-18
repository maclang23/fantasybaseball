import streamlit as st
import pandas as pd
import re
import io
import traceback
from espn_api.baseball import League

# --- STREAMLIT UI SETUP ---
st.set_page_config(page_title="MLB Roster Exporter", page_icon="⚾", layout="wide")

st.title("⚾ Fantasy Baseball Roster Exporter")
st.markdown("""
This tool connects to your ESPN League and generates a multi-tab Excel file containing:
1. **Individual Team Rosters** (One tab per team)
2. **Top 500 Free Agents**
3. **Master List** (All players in the league)
""")

# --- SIDEBAR: AUTHENTICATION (FLEXIBLE VERSION) ---
with st.sidebar:
    st.header("Authentication")
    
    # 1. Check if secrets actually exist in the dashboard
    has_secrets = "SWID" in st.secrets and "ESPN_S2" in st.secrets
    
    # 2. The Toggle
    use_defaults = st.checkbox("Use System Credentials", value=has_secrets, 
                               help="Uncheck to enter a different League ID or private credentials.")

    if use_defaults:
        if has_secrets:
            # Silently pull from secrets
            league_id = int(st.secrets.get("LEAGUE_ID", 11440))
            swid = st.secrets.get("SWID")
            espn_s2 = st.secrets.get("ESPN_S2")
            st.success("🔒 Using hidden system keys.")
        else:
            st.error("No secrets found in dashboard! Please enter credentials manually.")
            use_defaults = False # Fallback if you forgot to set secrets

    # 3. Manual Inputs (Only show if toggle is OFF)
    if not use_defaults:
        league_id = st.number_input("League ID", value=11440)
        swid = st.text_input("SWID", type="password", help="Enter your ESPN SWID")
        espn_s2 = st.text_input("ESPN_S2", type="password", help="Enter your ESPN_S2 cookie")

    # 4. Shared Settings
    year = st.number_input("Year", value=2026)
    
    st.divider()
    st.info("The Excel file will be generated based on the credentials selected above.")
# --- HELPER FUNCTIONS ---
def auto_adjust_column_width(writer, df, sheet_name):
    """Adjusts Excel column widths to fit content."""
    worksheet = writer.sheets[sheet_name]
    for col_idx, column in enumerate(df.columns):
        column_width = max(df[column].astype(str).map(len).max(), len(column))
        worksheet.column_dimensions[chr(65 + col_idx)].width = column_width + 2

# --- MAIN LOGIC ---
if st.button("🚀 Generate Excel Report"):
    try:
        with st.spinner("Connecting to ESPN API..."):
            league = League(league_id=league_id, year=year, espn_s2=espn_s2, swid=swid)
            
        st.success(f"Successfully connected to: **{league.settings.name}**")
        
        # We use BytesIO so the file is created in memory (necessary for web hosting)
        output = io.BytesIO()
        
        excluded_slots = {'UTIL', 'BE', 'IL', 'IF', 'LF', 'CF', 'RF', 'SP', 'RP'}
        all_players_master_list = []

        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            
            # 1. Process Teams
            progress_bar = st.progress(0)
            for i, team in enumerate(league.teams):
                roster_data = []
                for player in team.roster:
                    clean_slots = [slot for slot in player.eligibleSlots if slot not in excluded_slots]
                    player_info = {
                        "Player Name": player.name,
                        "Fantasy Team": team.team_name,
                        "Pro Team": player.proTeam,
                        "Injury Status": player.injuryStatus,
                        "Eligible Positions": ", ".join(clean_slots)
                    }
                    roster_data.append(player_info)
                    all_players_master_list.append(player_info)
                
                df_team = pd.DataFrame(roster_data)
                clean_sheet_name = re.sub(r'[\\/*?:\[\]]', '', team.team_name)[:31]
                df_team.to_excel(writer, sheet_name=clean_sheet_name, index=False)
                auto_adjust_column_width(writer, df_team, clean_sheet_name)
                
                # Update progress
                progress_bar.progress((i + 1) / len(league.teams))

            # 2. Process Free Agents
            with st.spinner("Fetching Top 500 Free Agents..."):
                try:
                    free_agents = league.free_agents(size=500)
                    fa_data = []
                    for player in free_agents:
                        clean_slots = [slot for slot in player.eligibleSlots if slot not in excluded_slots]
                        fa_data.append({
                            "Player Name": player.name,
                            "Fantasy Team": "Free Agent",
                            "Pro Team": player.proTeam,
                            "Injury Status": player.injuryStatus,
                            "Eligible Positions": ", ".join(clean_slots)
                        })
                    
                    df_fa = pd.DataFrame(fa_data)
                    df_fa.to_excel(writer, sheet_name="Free Agents", index=False)
                    auto_adjust_column_width(writer, df_fa, "Free Agents")
                    all_players_master_list.extend(fa_data)
                except Exception as e:
                    st.warning(f"Could not fetch Free Agents: {e}")

            # 3. Master Tab
            df_all = pd.DataFrame(all_players_master_list)
            if not df_all.empty:
                df_all = df_all.sort_values(by="Player Name")
                df_all.to_excel(writer, sheet_name="All Players Status", index=False)
                auto_adjust_column_width(writer, df_all, "All Players Status")

        # --- PREPARE DOWNLOAD ---
        excel_data = output.getvalue()
        file_name = f"{league.settings.name.replace(' ', '_')}_Roster_{year}.xlsx"
        
        st.balloons()
        st.subheader("✅ Extraction Complete")
        
        # Preview of the master list
        st.dataframe(df_all, use_container_width=True)

        st.download_button(
            label="📥 Download Excel File",
            data=excel_data,
            file_name=file_name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    except Exception as e:
        st.error("An error occurred during the process.")
        st.expander("Show Technical Error").code(traceback.format_exc())
