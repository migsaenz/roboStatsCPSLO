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
        
        # For tracking combined skills (programming + driver)
        self.combined_skills = []
        
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
            
        if self.combined_skills:
            self.skill_avg = sum(self.combined_skills) / len(self.combined_skills)
    
    def __str__(self):
        return (f"{self.code}: "
                f"Qual Avg={self.qual_avg:.2f}, "
                f"Best={self.best_qual}, "
                f"Elims Avg={self.elims_avg:.2f}, "
                f"Skill Avg={self.skill_avg:.2f}, "
                f"Combined Skills={self.combined_skills}")

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
    
    try:
        response = requests.get(url, headers=HEADERS, params=params)
        response.raise_for_status()  # This will raise an exception for 404 and other errors
        
        data = response.json()
        matches = data["data"]
        
        # Check for pagination
        if data["meta"]["last_page"] > 1:
            for page in range(2, data["meta"]["last_page"] + 1):
                params["page"] = page
                next_response = requests.get(url, headers=HEADERS, params=params)
                next_response.raise_for_status()
                matches.extend(next_response.json()["data"])
        
        return matches
    except requests.exceptions.RequestException as e:
        print(f"Error fetching matches for event {event_id}, team {team_id}: {e}")
        return []

def get_skills_results(event_id, team_id):
    """Get skills results for a team at an event"""
    url = f"{BASE_URL}/events/{event_id}/skills"
    params = {"team": team_id}
    
    skills = []
    try:
        response = requests.get(url, headers=HEADERS, params=params)
        response.raise_for_status()  # This will raise an exception for 404 and other errors
        
        data = response.json()
        if "data" not in data:
            print(f"Unexpected response format for skills: {data}")
            return []
            
        skills = data["data"]
        
        # Check for pagination
        if "meta" in data and data["meta"]["last_page"] > 1:
            for page in range(2, data["meta"]["last_page"] + 1):
                params["page"] = page
                next_response = requests.get(url, headers=HEADERS, params=params)
                next_response.raise_for_status()
                skills.extend(next_response.json().get("data", []))
        
        # Debug print the first skill to understand structure
        if skills and len(skills) > 0:
            print(f"    First skill data structure example: {skills[0]}")
        
        return skills
    except requests.exceptions.RequestException as e:
        print(f"Error fetching skills for event {event_id}, team {team_id}: {e}")
        return []

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

def extract_combined_skills(skills):
    """Extract and combine skills scores (programming + driver) from skills data"""
    # Print raw skills data for debugging
    print(f"    Raw skills data structure: {type(skills)}")
    if skills and len(skills) > 0:
        print(f"    First skill item type: {type(skills[0])}")
    
    # Group skills by run/attempt (each event typically has driver and programming)
    driver_skills = []
    programming_skills = []
    
    for skill in skills:
        try:
            if not isinstance(skill, dict):
                print(f"    Unexpected skill format: {skill}")
                continue
                
            # Extract the type and score
            skill_type = skill.get("type")
            score = skill.get("score", 0)
            
            if not isinstance(skill_type, dict):
                print(f"    Unexpected skill type format: {skill_type}")
                continue
                
            type_id = skill_type.get("id", 0)
            
            # Add to appropriate list
            if type_id == 1:  # Driver skills
                driver_skills.append(score)
            elif type_id == 2:  # Programming skills
                programming_skills.append(score)
        except Exception as e:
            print(f"    Error processing skill: {e}")
            continue
    
    print(f"    Processed driver skills: {driver_skills}")
    print(f"    Processed programming skills: {programming_skills}")
    
    # Find the best driver and programming scores
    best_driver = max(driver_skills) if driver_skills else 0
    best_programming = max(programming_skills) if programming_skills else 0
    
    # Return the combined score (if both are available) or individual scores
    if best_driver > 0 or best_programming > 0:
        combined_score = best_driver + best_programming
        print(f"    Combined skills score: {combined_score}")
        return [combined_score]
    else:
        return []

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
        
        # For VEX U events, we need a different approach for matches
        # The 404 errors indicate the matches endpoint might be different or not available
        # Let's try to get the rankings instead, which should have qualification data
        try:
            print(f"  Attempting to get rankings for event {event_id}")
            url = f"{BASE_URL}/events/{event_id}/rankings"
            params = {"team": team_id}
            
            response = requests.get(url, headers=HEADERS, params=params)
            response.raise_for_status()
            
            rankings_data = response.json()
            if "data" in rankings_data and rankings_data["data"]:
                for ranking in rankings_data["data"]:
                    if ranking["team"]["id"] == team_id:
                        # Extract qualification data from rankings
                        if "average_points" in ranking:
                            avg_points = ranking["average_points"]
                            team.qual_scores.append(avg_points)
                            print(f"    Found qualification average: {avg_points}")
                        
                        if "high_score" in ranking:
                            high_score = ranking["high_score"]
                            print(f"    Found high score: {high_score}")
                            # Check if this is the best score we've seen
                            if high_score > best_event_score:
                                best_event_score = high_score
                                best_event_name = event_name
            else:
                print(f"    No ranking data found for team at this event")
        except Exception as e:
            print(f"    Error getting rankings: {e}")
        
        # Get skills results - this seems to be working correctly
        try:
            skills = get_skills_results(event_id, team_id)
            
            # Group skills by type
            driver_scores = []
            programming_scores = []
            
            for skill in skills:
                if not isinstance(skill, dict):
                    continue
                    
                try:
                    skill_type = skill.get("type", {})
                    if not isinstance(skill_type, dict):
                        continue
                        
                    type_id = skill_type.get("id", 0)
                    score = skill.get("score", 0)
                    
                    if type_id == 1:  # Driver
                        driver_scores.append(score)
                    elif type_id == 2:  # Programming
                        programming_scores.append(score)
                except Exception as e:
                    print(f"      Error processing skill: {e}")
            
            print(f"    Driver skills scores: {driver_scores}")
            print(f"    Programming skills scores: {programming_scores}")
            
            # Calculate combined score for this event (best driver + best programming)
            best_driver = max(driver_scores) if driver_scores else 0
            best_programming = max(programming_scores) if programming_scores else 0
            
            if best_driver > 0 or best_programming > 0:
                combined_score = best_driver + best_programming
                print(f"    Combined skills score: {combined_score}")
                team.combined_skills.append(combined_score)
        except Exception as e:
            print(f"    Error processing skills: {e}")
        
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
    
    # Also save as CSV for easier viewing
    csv_file = output_file.replace(".txt", ".csv")
    with open(csv_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["Team", "Qual Avg", "Best Qual", "Elims Avg", "Skill Avg", 
                          "Best Team", "Best Score", "Best Event", "Best Event Score",
                          "Elims Team", "Elims Score", "Elims Avg Team", "Elims Avg Score",
                          "Skills Team", "Skills Score"])
        
        for team in sorted_teams:
            writer.writerow([
                team.code, team.qual_avg, team.best_qual, team.elims_avg, team.skill_avg,
                team.code, team.best_qual, team.best_event_name, team.best_event_score,
                team.code, team.elims_avg, team.code, team.elims_avg,
                team.code, team.skill_avg
            ])
    
    print(f"CSV saved to {csv_file}")

def main():
    print("RobotEvents API Spreadsheet Updater (Skills-Focused)")
    print("--------------------------------------------------")
    
    # Get API key
    api_key = input("Enter your RobotEvents API key: ")
    global HEADERS
    HEADERS = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }
    
    # Get season ID
    season_id = input("Enter the season ID (e.g., 191 for 2024-2025): ")
    
    # Choose operation mode
    print("\nChoose operation mode:")
    print("1. Parse existing spreadsheet and update with new data")
    print("2. Create new spreadsheet from scratch")
    mode = input("Enter choice (1 or 2): ")
    
    if mode == "1":
        # Parse existing spreadsheet
        file_path = input("Enter path to existing spreadsheet: ")
        # This would need implementation if used
        print("This feature is not fully implemented yet.")
        return
        
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
        
        # Choose sort option
        print("\nSort results by:")
        print("1. Skills Average (recommended)")
        print("2. Qualification Match Average")
        print("3. Best Qualification Score")
        sort_option = input("Enter choice (1, 2, or 3) [Default: 1]: ") or "1"
        
        sort_field = "skill_avg"  # Default
        if sort_option == "2":
            sort_field = "qual_avg"
        elif sort_option == "3":
            sort_field = "best_qual"
        
        # Generate new spreadsheet
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"robotics_teams_{timestamp}.txt"
        generate_spreadsheet(teams, output_file, sort_by=sort_field)
        
    else:
        print("Invalid choice.")

if __name__ == "__main__":
    main()
