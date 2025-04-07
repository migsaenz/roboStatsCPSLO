import requests
import pandas as pd
import numpy as np
import json
import os
from datetime import datetime

# Configuration
API_KEY = "YOUR_API_KEY_HERE"  # Replace with your RobotEvents API key
HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Accept": "application/json",
}
BASE_URL = "https://www.robotevents.com/api/v2"

class TeamData:
    def __init__(self, code):
        self.code = code
        self.qual_avg = 0
        self.best_qual = 0
        self.elims_avg = 0
        self.skill_avg = 0
        
        # Match data
        self.qual_scores = []
        self.elims_scores = []
        
        # Skills data
        self.driver_skills = []
        self.programming_skills = []
        self.combined_skills = []
        
        # Event data
        self.events = []
        self.best_event_name = ""
        self.best_event_score = 0

def get_team_info(team_code):
    """Get team information from RobotEvents API"""
    url = f"{BASE_URL}/teams"
    params = {"number": team_code}
    
    try:
        response = requests.get(url, headers=HEADERS, params=params)
        response.raise_for_status()
        
        data = response.json()
        if not data["data"]:
            print(f"Team {team_code} not found")
            return None
        
        return data["data"][0]
    except Exception as e:
        print(f"Error fetching team {team_code}: {e}")
        return None

def get_team_events(team_id, season_id):
    """Get all events for a team in a season"""
    url = f"{BASE_URL}/teams/{team_id}/events"
    params = {"season": season_id}
    
    events = []
    page = 1
    
    try:
        while True:
            params["page"] = page
            response = requests.get(url, headers=HEADERS, params=params)
            response.raise_for_status()
            
            data = response.json()
            events.extend(data["data"])
            
            if page >= data["meta"]["last_page"]:
                break
            
            page += 1
        
        return events
    except Exception as e:
        print(f"Error fetching events for team {team_id}: {e}")
        return events

def get_event_divisions(event_id):
    """Get divisions for an event - VEXU events often have divisions"""
    url = f"{BASE_URL}/events/{event_id}/divisions"
    
    try:
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        
        data = response.json()
        return data.get("data", [])
    except Exception as e:
        print(f"Error fetching divisions for event {event_id}: {e}")
        return []

def get_division_matches(event_id, division_id, team_id=None):
    """Get matches for a specific division in an event"""
    url = f"{BASE_URL}/events/{event_id}/divisions/{division_id}/matches"
    params = {}
    if team_id:
        params["team"] = team_id
    
    matches = []
    try:
        response = requests.get(url, headers=HEADERS, params=params)
        response.raise_for_status()
        
        data = response.json()
        matches.extend(data.get("data", []))
        
        # Check for pagination
        if "meta" in data and "last_page" in data["meta"] and data["meta"]["last_page"] > 1:
            for page in range(2, data["meta"]["last_page"] + 1):
                params["page"] = page
                response = requests.get(url, headers=HEADERS, params=params)
                response.raise_for_status()
                matches.extend(response.json().get("data", []))
        
        return matches
    except Exception as e:
        print(f"Error fetching division matches for event {event_id}, division {division_id}: {e}")
        return []

def get_event_matches(event_id, team_id=None):
    """Get matches for an event, trying multiple approaches"""
    matches = []
    
    # Approach 1: Try standard matches endpoint
    url = f"{BASE_URL}/events/{event_id}/matches"
    params = {}
    if team_id:
        params["team"] = team_id
    
    try:
        response = requests.get(url, headers=HEADERS, params=params)
        if response.status_code == 200:
            data = response.json()
            matches.extend(data.get("data", []))
            print(f"    Found {len(matches)} matches via standard endpoint")
            return matches
        else:
            print(f"    Standard matches endpoint returned status {response.status_code}")
    except Exception as e:
        print(f"    Error with standard matches endpoint: {e}")
    
    # Approach 2: Try to get divisions and then matches for each division
    divisions = get_event_divisions(event_id)
    if divisions:
        print(f"    Found {len(divisions)} divisions for event {event_id}")
        for division in divisions:
            division_id = division["id"]
            division_matches = get_division_matches(event_id, division_id, team_id)
            if division_matches:
                print(f"    Found {len(division_matches)} matches in division {division['name']}")
                matches.extend(division_matches)
    
    return matches

def get_team_skills(event_id, team_id):
    """Get skills results for a team at an event"""
    url = f"{BASE_URL}/events/{event_id}/skills"
    params = {"team": team_id}
    
    skills = []
    try:
        response = requests.get(url, headers=HEADERS, params=params)
        response.raise_for_status()
        
        data = response.json()
        skills.extend(data.get("data", []))
        
        # Check for pagination
        if "meta" in data and "last_page" in data["meta"] and data["meta"]["last_page"] > 1:
            for page in range(2, data["meta"]["last_page"] + 1):
                params["page"] = page
                response = requests.get(url, headers=HEADERS, params=params)
                response.raise_for_status()
                skills.extend(response.json().get("data", []))
        
        return skills
    except Exception as e:
        print(f"    Error getting skills: {e}")
        return []

def extract_scores_from_matches(matches, team_id):
    """Extract qualification and elimination scores from matches"""
    qual_scores = []
    elims_scores = []
    
    for match in matches:
        try:
            # Check if match has alliances
            if "alliances" not in match or len(match["alliances"]) < 2:
                continue
                
            # Find which alliance the team is on
            team_alliance = None
            for i, alliance in enumerate(match["alliances"]):
                for team in alliance.get("teams", []):
                    if team.get("id") == team_id:
                        team_alliance = i
                        break
                if team_alliance is not None:
                    break
            
            if team_alliance is None:
                continue
                
            # Get the score
            score = match["alliances"][team_alliance].get("score", 0)
            
            # Determine if qualification or elimination match
            round_num = match.get("round", 0)
            if round_num == 1:  # Qualification
                qual_scores.append(score)
            else:  # Elimination (round > 1)
                elims_scores.append(score)
                
        except Exception as e:
            print(f"      Error processing match: {e}")
    
    return qual_scores, elims_scores

def process_team_data(team_code, season_id):
    """Process all data for a team"""
    team = TeamData(team_code)
    
    # Get team information
    team_info = get_team_info(team_code)
    if not team_info:
        print(f"Team {team_code} not found in the API")
        return None
    
    team_id = team_info["id"]
    print(f"Found team {team_code} (ID: {team_id})")
    
    # Get all events for this team
    events = get_team_events(team_id, season_id)
    print(f"Found {len(events)} events for team {team_code}")
    
    # Process each event
    for event in events:
        event_id = event["id"]
        event_name = event["name"]
        print(f"  Processing event: {event_name}")
        
        # Store event data
        team.events.append({
            "id": event_id,
            "name": event_name,
            "start_date": event.get("start", ""),
            "end_date": event.get("end", "")
        })
        
        # Get matches for this event
        matches = get_event_matches(event_id, team_id)
        
        if matches:
            # Extract scores from matches
            qual_scores, elims_scores = extract_scores_from_matches(matches, team_id)
            
            team.qual_scores.extend(qual_scores)
            team.elims_scores.extend(elims_scores)
            
            print(f"    Qualification scores: {qual_scores}")
            print(f"    Elimination scores: {elims_scores}")
            
            # Update best score if needed
            if qual_scores:
                event_best = max(qual_scores)
                if event_best > team.best_event_score:
                    team.best_event_score = event_best
                    team.best_event_name = event_name
        
        # Get skills data
        skills = get_team_skills(event_id, team_id)
        
        if skills:
            print(f"    Found {len(skills)} skills runs")
            
            # Extract driver and programming skills
            driver_scores = []
            programming_scores = []
            
            for skill in skills:
                try:
                    skill_type = skill.get("type")
                    score = skill.get("score", 0)
                    
                    if skill_type == "driver":
                        driver_scores.append(score)
                        team.driver_skills.append(score)
                    elif skill_type == "programming":
                        programming_scores.append(score)
                        team.programming_skills.append(score)
                except Exception as e:
                    print(f"      Error processing skill: {e}")
            
            # Calculate combined score for this event (best driver + best programming)
            best_driver = max(driver_scores) if driver_scores else 0
            best_programming = max(programming_scores) if programming_scores else 0
            
            if best_driver > 0 or best_programming > 0:
                combined_score = best_driver + best_programming
                team.combined_skills.append(combined_score)
                print(f"    Best Driver: {best_driver}, Best Programming: {best_programming}")
                print(f"    Combined score: {combined_score}")
    
    # Calculate final statistics
    if team.qual_scores:
        team.qual_avg = sum(team.qual_scores) / len(team.qual_scores)
        team.best_qual = max(team.qual_scores)
    
    if team.elims_scores:
        team.elims_avg = sum(team.elims_scores) / len(team.elims_scores)
    
    if team.combined_skills:
        team.skill_avg = sum(team.combined_skills) / len(team.combined_skills)
    
    print(f"Team {team_code} summary:")
    print(f"  Qualification Average: {team.qual_avg:.2f}")
    print(f"  Best Qualification Score: {team.best_qual}")
    print(f"  Elimination Average: {team.elims_avg:.2f}")
    print(f"  Skills Average: {team.skill_avg:.2f}")
    print(f"  Best Event: {team.best_event_name} (Score: {team.best_event_score})")
    
    return team

def format_spreadsheet_row(team):
    """Format a row for the spreadsheet in the exact format as the example"""
    # Format to match the example spreadsheet
    return (f"{team.code} {team.qual_avg} {team.best_qual} {team.elims_avg} {team.skill_avg} "
            f"{team.code} {team.best_qual} {team.code} {team.best_qual} "
            f"{team.code} {team.elims_avg} {team.code} {team.elims_avg} "
            f"{team.code} {team.skill_avg} {team.code} {team.skill_avg}")

def generate_spreadsheet(teams, output_file):
    """Generate a spreadsheet in the exact format as the example"""
    # Sort teams by qualification average (highest first)
    sorted_teams = sorted(teams.values(), key=lambda t: t.qual_avg, reverse=True)
    
    with open(output_file, 'w') as f:
        for team in sorted_teams:
            row = format_spreadsheet_row(team)
            f.write(row + "\n")
    
    print(f"Spreadsheet saved to {output_file}")
    
    # Also save as CSV for easier viewing
    csv_file = output_file.replace(".txt", ".csv")
    with open(csv_file, 'w', newline='') as f:
        writer = pd.DataFrame([{
            "Team": team.code,
            "Qual Avg": team.qual_avg,
            "Best Qual": team.best_qual,
            "Elims Avg": team.elims_avg,
            "Skill Avg": team.skill_avg,
            "Events": len(team.events),
            "Driver Skills": max(team.driver_skills) if team.driver_skills else 0,
            "Programming Skills": max(team.programming_skills) if team.programming_skills else 0
        } for team in sorted_teams])
        writer.to_csv(csv_file, index=False)
    
    print(f"CSV saved to {csv_file}")

def main():
    print("VEXU Match and Skills Data Accessor")
    print("----------------------------------")
    
    # Get API key
    api_key = input("Enter your RobotEvents API key: ")
    global HEADERS
    HEADERS = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }
    
    # Get season ID
    season_id = input("Enter the season ID (e.g., 191 for 2024-2025): ")
    
    # Get team codes
    teams_input = input("Enter comma-separated team codes (without spaces after commas): ")
    team_codes = [code.strip() for code in teams_input.split(",")]
    
    teams = {}
    for code in team_codes:
        print(f"\nProcessing team {code}...")
        team = process_team_data(code, season_id)
        if team:
            teams[code] = team
    
    # Generate spreadsheet
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"vexu_teams_{timestamp}.txt"
    generate_spreadsheet(teams, output_file)

if __name__ == "__main__":
    main()