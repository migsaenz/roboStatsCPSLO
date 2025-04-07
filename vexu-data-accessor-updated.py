import requests
import pandas as pd
import numpy as np
import json
import os
from datetime import datetime
import time

# Configuration
API_KEY = "YOUR_API_KEY_HERE"  # Replace with your RobotEvents API key
HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Accept": "application/json",
}
BASE_URL = "https://www.robotevents.com/api/v2"

# Constants
VEXU_PROGRAM_ID = 41  # VEXU program ID

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

def api_request(url, params=None, retry_count=3):
    """Make an API request with retry logic and rate limiting"""
    for attempt in range(retry_count):
        try:
            response = requests.get(url, headers=HEADERS, params=params)
            
            # Check for rate limiting (status 429)
            if response.status_code == 429:
                wait_time = int(response.headers.get("Retry-After", 5))
                print(f"Rate limited. Waiting {wait_time} seconds...")
                time.sleep(wait_time)
                continue
                
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if response.status_code == 404:
                # Not found is a valid response in some cases
                print(f"Resource not found: {url}")
                return None
            elif attempt < retry_count - 1:
                print(f"HTTP error: {e}. Retrying ({attempt+1}/{retry_count})...")
                time.sleep(2)
            else:
                print(f"Max retries reached. HTTP error: {e}")
                return None
        except Exception as e:
            if attempt < retry_count - 1:
                print(f"Error: {e}. Retrying ({attempt+1}/{retry_count})...")
                time.sleep(2)
            else:
                print(f"Max retries reached. Error: {e}")
                return None
    
    return None

def get_team_info(team_code):
    """Get team information from RobotEvents API"""
    url = f"{BASE_URL}/teams"
    params = {"number": team_code}
    
    data = api_request(url, params)
    if not data or not data.get("data"):
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
        data = api_request(url, params)
        
        if not data:
            break
        
        events.extend(data.get("data", []))
        
        if page >= data["meta"]["last_page"]:
            break
        
        page += 1
    
    return events

def get_event_details(event_id):
    """Get detailed information about an event"""
    url = f"{BASE_URL}/events/{event_id}"
    return api_request(url)

def get_event_divisions(event_id):
    """Get divisions for an event - VEXU events often have divisions"""
    url = f"{BASE_URL}/events/{event_id}/divisions"
    
    data = api_request(url)
    if data:
        return data.get("data", [])
    return []

def get_division_matches(event_id, division_id, team_id=None):
    """Get matches for a specific division in an event"""
    url = f"{BASE_URL}/events/{event_id}/divisions/{division_id}/matches"
    params = {}
    if team_id:
        params["team"] = team_id
    
    matches = []
    page = 1
    
    while True:
        params["page"] = page
        data = api_request(url, params)
        
        if not data:
            break
        
        matches.extend(data.get("data", []))
        
        if "meta" not in data or page >= data["meta"]["last_page"]:
            break
        
        page += 1
    
    return matches

def explore_event_structure(event_id):
    """Explore the structure of an event to better understand available endpoints"""
    print(f"Exploring API structure for event {event_id}")
    
    # Get event details
    event_data = get_event_details(event_id)
    if not event_data:
        print(f"  Unable to retrieve event details")
        return
    
    event_data = event_data.get("data", {}) if "data" in event_data else event_data
    
    print(f"  Event name: {event_data.get('name')}")
    print(f"  Event type: {event_data.get('event_type')}")
    program = event_data.get('program', {})
    print(f"  Program: {program.get('name')} (ID: {program.get('id')})")
    
    # Check for available endpoints
    endpoints = [
        f"/events/{event_id}/matches",
        f"/events/{event_id}/divisions",
        f"/events/{event_id}/teams",
        f"/events/{event_id}/skills"
    ]
    
    for endpoint in endpoints:
        full_url = f"{BASE_URL}{endpoint}"
        response = requests.get(full_url, headers=HEADERS)
        print(f"  Endpoint {endpoint}: Status {response.status_code}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                if "data" in data and isinstance(data["data"], list):
                    print(f"    Found {len(data['data'])} items")
            except:
                print("    Could not parse response as JSON")

def get_event_matches(event_id, team_id=None):
    """Get matches for an event, trying multiple approaches optimized for VEXU"""
    matches = []
    
    # First, explore the event structure to understand what we're working with
    event_data = get_event_details(event_id)
    if not event_data:
        print(f"    Unable to retrieve event details")
        return matches
    
    event_data = event_data.get("data", {}) if "data" in event_data else event_data
    program_id = event_data.get("program", {}).get("id")
    is_vexu = program_id == VEXU_PROGRAM_ID
    
    if is_vexu:
        print(f"    Event is a VEXU event (Program ID: {program_id})")
    
    # First try the direct matches endpoint
    url = f"{BASE_URL}/events/{event_id}/matches"
    params = {}
    if team_id:
        params["team"] = team_id
    
    try:
        response = requests.get(url, headers=HEADERS, params=params)
        if response.status_code == 200:
            data = response.json()
            if "data" in data:
                matches.extend(data["data"])
                print(f"    Found {len(matches)} matches via standard endpoint")
                return matches
        else:
            print(f"    Standard matches endpoint returned status {response.status_code}")
    except Exception as e:
        print(f"    Error with standard matches endpoint: {e}")
    
    # If that didn't work, try to get divisions
    divisions = get_event_divisions(event_id)
    if divisions:
        print(f"    Found {len(divisions)} divisions for event {event_id}")
        for division in divisions:
            division_id = division["id"]
            division_matches = get_division_matches(event_id, division_id, team_id)
            if division_matches:
                print(f"    Found {len(division_matches)} matches in division {division['name']}")
                matches.extend(division_matches)
    
    # If we still don't have matches, try alternative endpoints for VEXU
    if not matches and is_vexu:
        # Try with rankings data to find divisions
        url = f"{BASE_URL}/events/{event_id}/divisions"
        rankings_data = api_request(url)
        if rankings_data and "data" in rankings_data:
            print(f"    Found {len(rankings_data['data'])} divisions through rankings endpoint")
            
            for division in rankings_data["data"]:
                division_id = division["id"]
                # Now try to get matches for this division
                div_url = f"{BASE_URL}/events/{event_id}/divisions/{division_id}/matches"
                div_params = {"team": team_id} if team_id else {}
                div_matches = api_request(div_url, div_params)
                
                if div_matches and "data" in div_matches:
                    print(f"    Found {len(div_matches['data'])} matches in division {division_id}")
                    matches.extend(div_matches["data"])
    
    return matches

def get_team_skills(event_id, team_id):
    """Get skills results for a team at an event"""
    url = f"{BASE_URL}/events/{event_id}/skills"
    params = {"team": team_id}
    
    skills = []
    page = 1
    
    while True:
        params["page"] = page
        data = api_request(url, params)
        
        if not data:
            break
        
        skills.extend(data.get("data", []))
        
        if "meta" not in data or page >= data["meta"]["last_page"]:
            break
        
        page += 1
    
    return skills

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
            if round_num == 1 or round_num == 2:  # Qualification (some APIs use 1, some use 2)
                qual_scores.append(score)
            elif round_num > 2:  # Elimination (round > 2)
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
        print(f"  Processing event: {event_name} (ID: {event_id})")
        
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
    print(f"  # of Qual Matches: {len(team.qual_scores)}")
    print(f"  # of Elim Matches: {len(team.elims_scores)}")
    print(f"  # of Events with Match Data: {sum(1 for e in team.events if any(s in e['name'] for s in ['Tournament', 'Competition', 'Championship']))}")
    
    return team

def format_spreadsheet_row(team):
    """Format a row for the spreadsheet in the exact format as the example"""
    # Check if we have match data - if not, warn the user
    has_match_data = len(team.qual_scores) > 0 or len(team.elims_scores) > 0
    
    if not has_match_data:
        print(f"Warning: No match data found for team {team.code}. Using skills data only.")
    
    # Format to match the example spreadsheet
    return (f"{team.code} {team.qual_avg:.2f} {team.best_qual} {team.elims_avg:.2f} {team.skill_avg:.2f} "
            f"{team.code} {team.best_qual} {team.code} {team.best_qual} "
            f"{team.code} {team.elims_avg:.2f} {team.code} {team.elims_avg:.2f} "
            f"{team.code} {team.skill_avg:.2f} {team.code} {team.skill_avg:.2f}")

def generate_spreadsheet(teams, output_file):
    """Generate a spreadsheet in the exact format as the example"""
    # Sort teams by qualification average (highest first)
    # If qualification average is 0, sort by skills average
    def sort_key(team):
        if team.qual_avg > 0:
            return (team.qual_avg, team.skill_avg)
        else:
            return (0, team.skill_avg)
    
    sorted_teams = sorted(teams.values(), key=sort_key, reverse=True)
    
    with open(output_file, 'w') as f:
        for team in sorted_teams:
            row = format_spreadsheet_row(team)
            f.write(row + "\n")
    
    print(f"Spreadsheet saved to {output_file}")
    
    # Also save as CSV for easier viewing
    csv_file = output_file.replace(".txt", ".csv")
    csv_data = []
    for team in sorted_teams:
        csv_data.append({
            "Team": team.code,
            "Qual Avg": team.qual_avg,
            "Best Qual": team.best_qual,
            "Elims Avg": team.elims_avg,
            "Skill Avg": team.skill_avg,
            "Events": len(team.events),
            "Driver Skills": max(team.driver_skills) if team.driver_skills else 0,
            "Programming Skills": max(team.programming_skills) if team.programming_skills else 0,
            "Qual Matches": len(team.qual_scores),
            "Elim Matches": len(team.elims_scores)
        })
    
    df = pd.DataFrame(csv_data)
    df.to_csv(csv_file, index=False)
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
