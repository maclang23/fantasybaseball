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

# --- SIDEBAR: AUTHENTICATION (SECURE VERSION) ---
with st.sidebar:
    st.header("Settings")
    
    # 1. Get secrets silently
    sec_id = st.secrets.get("LEAGUE_ID")
    sec_swid = st.secrets.get("SWID")
    sec_s2 = st.secrets.get("ESPN_S2")

    # 2. Setup variables
    # If the secret exists, use it. If not, show an input box.
    if sec_id:
        league_id = int(sec_id)
        st.success("✅ League ID loaded from system.")
    else:
        league_id = st.number_input("League ID", value=11440)

    year = st.number_input("Year", value=2026)

    # Use the secrets for SWID and S2 if they exist, 
    # otherwise provide a blank password field for the user.
    swid = sec_swid if sec_swid else st.text_input("SWID", type="password")
    espn_s2 = sec_s2 if sec_s2 else st.text_input("ESPN_S2", type="password")

    if sec_swid and sec_s2:
        st.info("🔒 Credentials are encrypted and hidden.")
    
    st.divider()
    st.markdown("Click the button below to generate the report using the hidden system credentials.")
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
