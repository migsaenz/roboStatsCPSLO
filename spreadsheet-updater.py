import requests
import pandas as pd
import numpy as np
import csv
import re
import os
import json
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
        
        # Store all score collections
        self.qual_scores = []
        self.elims_scores = []
        self.skill_scores = []
        
        # For best scores tracking
        self.best_event_name = ""
        self.best_event_score = 0
        
    def calculate_stats(self):
        """Calculate all statistics from collected scores"""
        if self.qual_scores:
            self.qual_avg = sum(self.qual_scores) / len(self.qual_scores)
            self.best_qual = max(self.qual_scores)
        
        if self.elims_scores:
            self.elims_avg = sum(self.elims_scores) / len(self.elims_scores)
            
        if self.skill_scores:
            self.skill_avg = sum(self.skill_scores) / len(self.skill_scores)
    
    def __str__(self):
        return (f"{self.code}: "
                f"Qual Avg={self.qual_avg:.2f}, "
                f"Best={self.best_qual}, "
                f"Elims Avg={self.elims_avg:.2f}, "
                f"Skill Avg={self.skill_avg:.2f}")

def parse_existing_spreadsheet(file_path):
    """Parse the existing spreadsheet to get team codes and data"""
    teams = {}
    
    with open(file_path, 'r') as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) < 5:
                continue
                
            # Check if this looks like a team entry (starts with letters)
            if not re.match(r'^[A-Za-z]+', parts[0]):
                continue
                
            try:
                code = parts[0]
                qual_avg = float(parts[1])
                best_qual = int(parts[2])
                elims_avg = float(parts[3])
                skill_avg = float(parts[4])
                
                team = TeamData(code)
                team.qual_avg = qual_avg
                team.best_qual = best_qual
                team.elims_avg = elims_avg
                team.skill_avg = skill_avg
                
                teams[code] = team
                
            except (ValueError, IndexError) as e:
                print(f"Error parsing line: {line.strip()}")
                print(f"Error details: {e}")
    
    print(f"Parsed {len(teams)} teams from {file_path}")
    return teams

def get_team_info(team_code):
    """Get team information from RobotEvents API"""
    url = f"{BASE_URL}/teams"
    params = {"number": team_code}
    
    response = requests.get(url, headers=HEADERS, params=params)
    
    if response.status_code != 200:
        print(f"Error fetching team {team_code}: {response.status_code}")
        return None
    
    data = response.json()
    if not data["data"]:
        print(f"Team {team_code} not found")
        return None
    
    return data["data"][0]

def get_team_events(team_id, season_id):
    """Get all events for a team in a season"""
    url = f"{BASE_URL}/teams/{team_id}/events"
    params = {"season": season_id}
    
    events = []
    page = 1
    
    while True:
        params["page"] = page
        response = requests.get(url, headers=HEADERS, params=params)
        
        if response.status_code != 200:
            print(f"Error fetching events for team {team_id}: {response.status_code}")
            break
        
        data = response.json()
        events.extend(data["data"])
        
        if page >= data["meta"]["last_page"]:
            break
        
        page += 1
    
    return events

def get_match_results(event_id, team_id):
    """Get match results for a team at an event"""
    url = f"{BASE_URL}/events/{event_id}/matches"
    params = {"team": team_id}
    
    matches = []
    page = 1
    
    while True:
        params["page"] = page
        response = requests.get(url, headers=HEADERS, params=params)
        
        if response.status_code != 200:
            print(f"Error fetching matches for event {event_id}, team {team_id}: {response.status_code}")
            break
        
        data = response.json()
        matches.extend(data["data"])
        
        if page >= data["meta"]["last_page"]:
            break
        
        page += 1
    
    return matches

def get_skills_results(event_id, team_id):
    """Get skills results for a team at an event"""
    url = f"{BASE_URL}/events/{event_id}/skills"
    params = {"team": team_id}
    
    skills = []
    page = 1
    
    while True:
        params["page"] = page
        response = requests.get(url, headers=HEADERS, params=params)
        
        if response.status_code != 200:
            print(f"Error fetching skills for event {event_id}, team {team_id}: {response.status_code}")
            break
        
        data = response.json()
        skills.extend(data["data"])
        
        if page >= data["meta"]["last_page"]:
            break
        
        page += 1
    
    return skills

def extract_scores(matches, team_id):
    """Extract scores from match data"""
    qual_scores = []
    elims_scores = []
    
    for match in matches:
        try:
            # Find which alliance the team is on
            red_teams = [t["id"] for t in match["alliances"][0]["teams"]]
            blue_teams = [t["id"] for t in match["alliances"][1]["teams"]]
            
            team_on_red = team_id in red_teams
            team_on_blue = team_id in blue_teams
            
            if not (team_on_red or team_on_blue):
                continue
            
            # Get the alliance score
            alliance_idx = 0 if team_on_red else 1
            score = match["alliances"][alliance_idx]["score"]
            
            # Add to appropriate list based on round
            if match["round"] == 1:  # Qualification
                qual_scores.append(score)
            else:  # Elimination
                elims_scores.append(score)
                
        except (KeyError, IndexError) as e:
            print(f"Error processing match: {e}")
            continue
    
    return qual_scores, elims_scores

def extract_skills_scores(skills):
    """Extract scores from skills data"""
    scores = []
    
    for skill in skills:
        try:
            if "score" in skill:
                scores.append(skill["score"])
        except Exception as e:
            print(f"Error processing skill: {e}")
            continue
    
    return scores

def fetch_team_data(team_code, season_id):
    """Fetch all data for a team from the API"""
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
    
    best_event_score = 0
    best_event_name = ""
    
    # Process each event
    for event in events:
        event_id = event["id"]
        event_name = event["name"]
        print(f"  Processing event: {event_name}")
        
        # Get match results
        matches = get_match_results(event_id, team_id)
        qual_scores, elims_scores = extract_scores(matches, team_id)
        team.qual_scores.extend(qual_scores)
        team.elims_scores.extend(elims_scores)
        
        # Check for best event score
        if qual_scores:
            event_best = max(qual_scores)
            if event_best > best_event_score:
                best_event_score = event_best
                best_event_name = event_name
        
        # Get skills results
        skills = get_skills_results(event_id, team_id)
        skill_scores = extract_skills_scores(skills)
        team.skill_scores.extend(skill_scores)
        
        print(f"    Qual scores: {qual_scores}")
        print(f"    Elims scores: {elims_scores}")
        print(f"    Skill scores: {skill_scores}")
    
    # Calculate statistics
    team.calculate_stats()
    team.best_event_name = best_event_name
    team.best_event_score = best_event_score
    
    print(f"Team {team_code} stats: {team}")
    return team

def format_spreadsheet_row(team, include_event_data=True):
    """Format a row for the spreadsheet in the exact format as the example"""
    if include_event_data:
        # Format with event data
        return (f"{team.code} {team.qual_avg} {team.best_qual} {team.elims_avg} {team.skill_avg} "
                f"{team.code} {team.best_qual} {team.best_event_name} {team.best_event_score} "
                f"{team.code} {team.elims_avg} {team.code} {team.elims_avg} "
                f"{team.code} {team.skill_avg} {team.code} {team.skill_avg}")
    else:
        # Simple format without event data
        return f"{team.code} {team.qual_avg} {team.best_qual} {team.elims_avg} {team.skill_avg}"

def generate_spreadsheet(teams, output_file, sort_by="qual_avg"):
    """Generate a spreadsheet in the exact format as the example"""
    # Sort teams by the specified field
    sorted_teams = sorted(teams.values(), key=lambda t: getattr(t, sort_by), reverse=True)
    
    with open(output_file, 'w') as f:
        for team in sorted_teams:
            row = format_spreadsheet_row(team)
            f.write(row + "\n")
    
    print(f"Spreadsheet saved to {output_file}")

def main():
    print("RobotEvents API Spreadsheet Updater")
    print("----------------------------------")
    
    # Get API key
    api_key = input("Enter your RobotEvents API key: ")
    global HEADERS
    HEADERS = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }
    
    # Get season ID
    season_id = input("Enter the season ID (e.g., 181 for 2024-2025): ")
    
    # Choose operation mode
    print("\nChoose operation mode:")
    print("1. Parse existing spreadsheet and update with new data")
    print("2. Create new spreadsheet from scratch")
    mode = input("Enter choice (1 or 2): ")
    
    if mode == "1":
        # Parse existing spreadsheet
        file_path = input("Enter path to existing spreadsheet: ")
        teams = parse_existing_spreadsheet(file_path)
        
        # Ask which teams to update
        update_all = input("Update all teams? (y/n): ").lower() == 'y'
        
        if update_all:
            teams_to_update = list(teams.keys())
        else:
            teams_input = input("Enter comma-separated team codes to update: ")
            teams_to_update = [code.strip() for code in teams_input.split(",")]
        
        # Update each team
        for code in teams_to_update:
            if code in teams:
                print(f"\nUpdating team {code}...")
                updated_team = fetch_team_data(code, season_id)
                if updated_team:
                    teams[code] = updated_team
            else:
                print(f"\nAdding new team {code}...")
                new_team = fetch_team_data(code, season_id)
                if new_team:
                    teams[code] = new_team
        
        # Generate updated spreadsheet
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"updated_spreadsheet_{timestamp}.txt"
        generate_spreadsheet(teams, output_file)
        
    elif mode == "2":
        # Create new spreadsheet
        teams_input = input("Enter comma-separated team codes: ")
        team_codes = [code.strip() for code in teams_input.split(",")]
        
        teams = {}
        for code in team_codes:
            print(f"\nFetching data for team {code}...")
            team = fetch_team_data(code, season_id)
            if team:
                teams[code] = team
        
        # Generate new spreadsheet
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"new_spreadsheet_{timestamp}.txt"
        generate_spreadsheet(teams, output_file)
        
    else:
        print("Invalid choice.")

if __name__ == "__main__":
    main()
