import requests
import json
import os
from datetime import datetime
import argparse

class RobotEventsExplorer:
    """Tool to explore the RobotEvents API and understand its structure"""
    
    def __init__(self, api_key):
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
        }
        self.base_url = "https://www.robotevents.com/api/v2"
        self.output_dir = "api_output"
        
        # Create output directory if it doesn't exist
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
    
    def make_request(self, endpoint, params=None):
        """Make a request to the API and return the JSON response"""
        url = f"{self.base_url}/{endpoint}"
        
        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()  # Raise an exception for 4XX/5XX responses
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error making request to {url}: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response status code: {e.response.status_code}")
                print(f"Response body: {e.response.text}")
            return None
    
    def explore_endpoint(self, endpoint, params=None, save=True):
        """Explore an API endpoint and optionally save the response to a file"""
        print(f"Exploring endpoint: {endpoint}")
        
        if params:
            param_str = ", ".join(f"{k}={v}" for k, v in params.items())
            print(f"Parameters: {param_str}")
        
        response = self.make_request(endpoint, params)
        
        if not response:
            print("No response received.")
            return None
        
        # Print some basic info about the response
        if "meta" in response:
            meta = response["meta"]
            print(f"Total records: {meta.get('total')}")
            print(f"Per page: {meta.get('per_page')}")
            print(f"Current page: {meta.get('current_page')}")
            print(f"Last page: {meta.get('last_page')}")
            print(f"First page URL: {meta.get('first_page_url')}")
        
        # Print data structure (for first item only)
        if "data" in response and response["data"]:
            first_item = response["data"][0]
            print("\nData structure (first item):")
            self.print_nested_keys(first_item)
        
        # Save to file if requested
        if save:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            endpoint_file = endpoint.replace("/", "_")
            filename = f"{self.output_dir}/{endpoint_file}"
            
            if params:
                param_file = "_".join(f"{k}_{v}" for k, v in params.items())
                filename += f"_{param_file}"
            
            filename += f"_{timestamp}.json"
            
            with open(filename, 'w') as f:
                json.dump(response, f, indent=2)
            
            print(f"Response saved to {filename}")
        
        return response
    
    def print_nested_keys(self, obj, prefix="", max_depth=3, current_depth=0):
        """Print the keys of a nested object with proper indentation"""
        if current_depth >= max_depth:
            print(f"{prefix}...")
            return
        
        if isinstance(obj, dict):
            for key, value in obj.items():
                if isinstance(value, (dict, list)) and value:
                    print(f"{prefix}{key}:")
                    self.print_nested_keys(value, prefix + "  ", max_depth, current_depth + 1)
                else:
                    print(f"{prefix}{key}: {type(value).__name__}")
        elif isinstance(obj, list) and obj:
            print(f"{prefix}[0]:")
            self.print_nested_keys(obj[0], prefix + "  ", max_depth, current_depth + 1)
    
    def list_programs(self):
        """List all available programs"""
        return self.explore_endpoint("programs")
    
    def list_seasons(self, program_id=None):
        """List all seasons or seasons for a specific program"""
        params = {}
        if program_id:
            params["program"] = program_id
        
        return self.explore_endpoint("seasons", params)
    
    def list_events(self, program_id=None, season_id=None):
        """List events, optionally filtered by program and/or season"""
        params = {}
        if program_id:
            params["program"] = program_id
        if season_id:
            params["season"] = season_id
        
        return self.explore_endpoint("events", params)
    
    def get_event_details(self, event_id):
        """Get details for a specific event"""
        return self.explore_endpoint(f"events/{event_id}")
    
    def list_teams(self, program_id=None, grade=None):
        """List teams, optionally filtered by program and/or grade"""
        params = {}
        if program_id:
            params["program"] = program_id
        if grade:
            params["grade"] = grade
        
        return self.explore_endpoint("teams", params)
    
    def get_team_details(self, team_id):
        """Get details for a specific team"""
        return self.explore_endpoint(f"teams/{team_id}")
    
    def list_team_events(self, team_id, season_id=None):
        """List events for a specific team, optionally filtered by season"""
        params = {}
        if season_id:
            params["season"] = season_id
        
        return self.explore_endpoint(f"teams/{team_id}/events", params)
    
    def list_event_divisions(self, event_id):
        """List divisions for a specific event"""
        return self.explore_endpoint(f"events/{event_id}/divisions")
    
    def list_event_teams(self, event_id, division_id=None):
        """List teams for a specific event, optionally filtered by division"""
        params = {}
        if division_id:
            params["division"] = division_id
        
        return self.explore_endpoint(f"events/{event_id}/teams", params)
    
    def list_event_matches(self, event_id, division_id=None, team_id=None, round_id=None):
        """List matches for a specific event, with optional filters"""
        params = {}
        if division_id:
            params["division"] = division_id
        if team_id:
            params["team"] = team_id
        if round_id:
            params["round"] = round_id
        
        return self.explore_endpoint(f"events/{event_id}/matches", params)
    
    def list_event_rankings(self, event_id, division_id=None, team_id=None):
        """List rankings for a specific event, with optional filters"""
        params = {}
        if division_id:
            params["division"] = division_id
        if team_id:
            params["team"] = team_id
        
        return self.explore_endpoint(f"events/{event_id}/rankings", params)
    
    def list_event_skills(self, event_id, division_id=None, team_id=None, type_id=None):
        """List skills results for a specific event, with optional filters"""
        params = {}
        if division_id:
            params["division"] = division_id
        if team_id:
            params["team"] = team_id
        if type_id:
            params["type"] = type_id
        
        return self.explore_endpoint(f"events/{event_id}/skills", params)
    
    def list_event_awards(self, event_id, division_id=None, team_id=None):
        """List awards for a specific event, with optional filters"""
        params = {}
        if division_id:
            params["division"] = division_id
        if team_id:
            params["team"] = team_id
        
        return self.explore_endpoint(f"events/{event_id}/awards", params)

def main():
    parser = argparse.ArgumentParser(description="Explore the RobotEvents API")
    parser.add_argument("--api-key", required=True, help="RobotEvents API key")
    parser.add_argument("--endpoint", choices=[
        "programs", "seasons", "events", "event", "teams", "team",
        "team-events", "divisions", "event-teams", "matches",
        "rankings", "skills", "awards"
    ], required=True, help="API endpoint to explore")
    parser.add_argument("--id", help="ID for specific endpoints (event, team)")
    parser.add_argument("--program", help="Program ID for filtering")
    parser.add_argument("--season", help="Season ID for filtering")
    parser.add_argument("--division", help="Division ID for filtering")
    parser.add_argument("--team", help="Team ID for filtering")
    parser.add_argument("--round", help="Round ID for filtering")
    parser.add_argument("--type", help="Type ID for filtering skills")
    parser.add_argument("--grade", help="Grade level for filtering teams")
    parser.add_argument("--no-save", action="store_true", help="Don't save response to file")
    
    args = parser.parse_args()
    
    explorer = RobotEventsExplorer(args.api_key)
    
    if args.endpoint == "programs":
        explorer.list_programs()
    
    elif args.endpoint == "seasons":
        explorer.list_seasons(args.program)
    
    elif args.endpoint == "events":
        explorer.list_events(args.program, args.season)
    
    elif args.endpoint == "event":
        if not args.id:
            print("Error: --id is required for event endpoint")
            return
        explorer.get_event_details(args.id)
    
    elif args.endpoint == "teams":
        explorer.list_teams(args.program, args.grade)
    
    elif args.endpoint == "team":
        if not args.id:
            print("Error: --id is required for team endpoint")
            return
        explorer.get_team_details(args.id)
    
    elif args.endpoint == "team-events":
        if not args.id:
            print("Error: --id is required for team-events endpoint")
            return
        explorer.list_team_events(args.id, args.season)
    
    elif args.endpoint == "divisions":
        if not args.id:
            print("Error: --id is required for divisions endpoint")
            return
        explorer.list_event_divisions(args.id)
    
    elif args.endpoint == "event-teams":
        if not args.id:
            print("Error: --id is required for event-teams endpoint")
            return
        explorer.list_event_teams(args.id, args.division)
    
    elif args.endpoint == "matches":
        if not args.id:
            print("Error: --id is required for matches endpoint")
            return
        explorer.list_event_matches(args.id, args.division, args.team, args.round)
    
    elif args.endpoint == "rankings":
        if not args.id:
            print("Error: --id is required for rankings endpoint")
            return
        explorer.list_event_rankings(args.id, args.division, args.team)
    
    elif args.endpoint == "skills":
        if not args.id:
            print("Error: --id is required for skills endpoint")
            return
        explorer.list_event_skills(args.id, args.division, args.team, args.type)
    
    elif args.endpoint == "awards":
        if not args.id:
            print("Error: --id is required for awards endpoint")
            return
        explorer.list_event_awards(args.id, args.division, args.team)

if __name__ == "__main__":
    main()