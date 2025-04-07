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
        
        # Raw data storage
        self.qual_scores = []
        self.elims_scores = []
        self.driver_skills = []
        self.programming_skills = []
        self.combined_skills = []
        
        # Event tracking
        self.best_event_name = ""
        self.best_event_score = 0
    
    def calculate_stats(self):
        """Calculate statistics from collected data"""
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
                f"Skill Avg={self.skill_avg:.2f}")

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
        return events  # Return any events we've already collected

def get_team_rankings(event_id, team_id):
    """Get rankings for a team at an event"""
    url = f"{BASE_URL}/events/{event_id}/rankings"
    params = {"team": team_id}
    
    try:
        response = requests.get(url, headers=HEADERS, params=params)
        response.raise_for_status()
        
        data = response.json()
        return data.get("data", [])
    except Exception as e:
        print(f"    Error getting rankings: {e}")
        return []

def get_team_matches(event_id, team_id):
    """Get match results for a team at an event"""
    url = f"{BASE_URL}/events/{event_id}/matches"
    params = {"team": team_id}
    
    try:
        response = requests.get(url, headers=HEADERS, params=params)
        response.raise_for_status()
        
        data = response.json()
        matches = data.get("data", [])
        
        # Check for pagination
        if "meta" in data and data["meta"]["last_page"] > 1:
            for page in range(2, data["meta"]["last_page"] + 1):
                params["page"] = page
                next_response = requests.get(url, headers=HEADERS, params=params)
                next_response.raise_for_status()
                matches.extend(next_response.json().get("data", []))
        
        return matches
    except Exception as e:
        print(f"    Error getting matches: {e}")
        return []

def get_team_skills(event_id, team_id):
    """Get skills results for a team at an event"""
    url = f"{BASE_URL}/events/{event_id}/skills"
    params = {"team": team_id}
    
    try:
        response = requests.get(url, headers=HEADERS, params=params)
        response.raise_for_status()
        
        data = response.json()
        skills = data.get("data", [])
        
        # Check for pagination
        if "meta" in data and data["meta"]["last_page"] > 1:
            for page in range(2, data["meta"]["last_page"] + 1):
                params["page"] = page
                next_response = requests.get(url, headers=HEADERS, params=params)
                next_response.raise_for_status()
                skills.extend(next_response.json().get("data", []))
        
        return skills
    except Exception as e:
        print(f"    Error getting skills: {e}")
        return []

def extract_match_scores(matches, team_id):
    """Extract qualification and elimination scores from matches"""
    qual_scores = []
    elims_scores = []
    
    for match in matches:
        try:
            # Find which alliance the team is on
            team_found = False
            team_alliance = None
            
            for i, alliance in enumerate(match.get("alliances", [])):
                for team in alliance.get("teams", []):
                    if team.get("id") == team_id:
                        team_found = True
                        team_alliance = i
                        break
                if team_found:
                    break
            
            if not team_found or team_alliance is None:
                continue
            
            # Get the score
            score = match["alliances"][team_alliance].get("score", 0)
            
            # Determine if qualification or elimination match
            round_num = match.get("round", 0)
            if round_num == 1:  # Qualification
                qual_scores.append(score)
            else:  # Elimination
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
        
        # Try to get qualification data from various sources
        
        # Method 1: Try to get rankings
        rankings = get_team_rankings(event_id, team_id)
        for ranking in rankings:
            if ranking.get("team", {}).get("id") == team_id:
                if "average_points" in ranking:
                    avg_points = ranking["average_points"]
                    team.qual_scores.append(avg_points)
                    print(f"    Found qualification average from rankings: {avg_points}")
                
                if "high_score" in ranking:
                    high_score = ranking["high_score"]
                    print(f"    Found high score from rankings: {high_score}")
                    if high_score > team.best_event_score:
                        team.best_event_score = high_score
                        team.best_event_name = event_name
        
        # Method 2: Try to get match data
        matches = get_team_matches(event_id, team_id)
        if matches:
            print(f"    Found {len(matches)} matches")
            qual_scores, elim_scores = extract_match_scores(matches, team_id)
            
            if qual_scores:
                print(f"    Qualification scores: {qual_scores}")
                team.qual_scores.extend(qual_scores)
                
                # Update best score if needed
                event_best = max(qual_scores)
                if event_best > team.best_event_score:
                    team.best_event_score = event_best
                    team.best_event_name = event_name
            
            if elim_scores:
                print(f"    Elimination scores: {elim_scores}")
                team.elims_scores.extend(elim_scores)
        
        # Get skills data
        skills = get_team_skills(event_id, team_id)
        if skills:
            print(f"    Found {len(skills)} skills runs")
            
            # Based on the actual API format, the skills data structure has
            # a "type" field that is a string ("driver" or "programming")
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
            
            if driver_scores:
                print(f"    Driver skills scores: {driver_scores}")
            
            if programming_scores:
                print(f"    Programming skills scores: {programming_scores}")
            
            # Calculate combined score for this event (best driver + best programming)
            best_driver = max(driver_scores) if driver_scores else 0
            best_programming = max(programming_scores) if programming_scores else 0
            
            if best_driver > 0 or best_programming > 0:
                combined_score = best_driver + best_programming
                print(f"    Combined skills score: {combined_score}")
                team.combined_skills.append(combined_score)
    
    # Calculate final statistics
    team.calculate_stats()
    
    print(f"Team {team_code} summary:")
    print(f"  Qualification Average: {team.qual_avg:.2f}")
    print(f"  Best Qualification Score: {team.best_qual}")
    print(f"  Elimination Average: {team.elims_avg:.2f}")
    print(f"  Best Driver Skill: {max(team.driver_skills) if team.driver_skills else 0}")
    print(f"  Best Programming Skill: {max(team.programming_skills) if team.programming_skills else 0}")
    print(f"  Combined Skills Average: {team.skill_avg:.2f}")
    print(f"  Best Event: {team.best_event_name} (Score: {team.best_event_score})")
    
    return team

def format_spreadsheet_row(team):
    """Format a row for the spreadsheet in the exact format as the example"""
    # Format with event data
    return (f"{team.code} {team.qual_avg} {team.best_qual} {team.elims_avg} {team.skill_avg} "
            f"{team.code} {team.best_qual} {team.best_event_name} {team.best_event_score} "
            f"{team.code} {team.elims_avg} {team.code} {team.elims_avg} "
            f"{team.code} {team.skill_avg} {team.code} {team.skill_avg}")

def generate_spreadsheet(teams, output_file, sort_by="skill_avg"):
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
                          "Elims Team", "Elims Avg", "Elims Avg Team", "Elims Avg Score",
                          "Skills Team", "Skills Score"])
        
        for team in sorted_teams:
            writer.writerow([
                team.code, 
                f"{team.qual_avg:.2f}", 
                team.best_qual, 
                f"{team.elims_avg:.2f}", 
                f"{team.skill_avg:.2f}",
                team.code, 
                team.best_qual, 
                team.best_event_name, 
                team.best_event_score,
                team.code, 
                f"{team.elims_avg:.2f}", 
                team.code, 
                f"{team.elims_avg:.2f}",
                team.code, 
                f"{team.skill_avg:.2f}"
            ])
    
    print(f"CSV saved to {csv_file}")

def main():
    print("RobotEvents API Teams Data Generator")
    print("-----------------------------------")
    
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
    print("1. Parse existing spreadsheet and update with new data (not implemented yet)")
    print("2. Create new spreadsheet from scratch")
    mode = input("Enter choice (1 or 2): ")
    
    if mode == "1":
        print("This feature is not implemented yet.")
        return
        
    elif mode == "2":
        # Create new spreadsheet
        teams_input = input("Enter comma-separated team codes (without spaces after commas): ")
        team_codes = [code.strip() for code in teams_input.split(",")]
        
        teams = {}
        for code in team_codes:
            print(f"\nProcessing team {code}...")
            team = process_team_data(code, season_id)
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
