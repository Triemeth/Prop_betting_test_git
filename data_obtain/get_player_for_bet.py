import pandas as pd
from nba_api.stats.static import players
from nba_api.stats.static import teams
from nba_api.stats.endpoints import leaguegamefinder
from nba_api.stats.endpoints import leagueleaders
from sklearn.preprocessing import LabelEncoder
import re
from nba_api.stats.endpoints import playergamelog
import requests
from nba_api.stats.static import teams
from nba_api.stats.endpoints import commonteamroster

# Custom requests.get function with extended timeout
original_get = requests.get

def custom_get(*args, **kwargs):
    kwargs['timeout'] = 30  # Set the timeout to 30 seconds
    return original_get(*args, **kwargs)

requests.get = custom_get

#calculate the Player effciency rating average for the leaguge
def clac_avg_PER(league_avg_stats):
    points = league_avg_stats['PTS'].mean()
    fga = league_avg_stats['FGA'].mean()
    fta = league_avg_stats['FTA'].mean()
    tov = league_avg_stats['TOV'].mean()
    reb = league_avg_stats['REB'].mean()
    ast = league_avg_stats['AST'].mean()
    blk = league_avg_stats['BLK'].mean()
    stl = league_avg_stats['STL'].mean()
    pf = league_avg_stats['PF'].mean()

    missed_fg = (fga - league_avg_stats['FGM'].mean())
    missed_ft = (fta - league_avg_stats['FTM'].mean())

    player_efficiency_avg = (
        points + reb + ast + stl + blk - missed_fg - missed_ft - tov - pf
    )

    return player_efficiency_avg

#calculate the individual Player efficiency rating
def calc_PER(player_stats, league_avg_stats):
    player_efficiency_avg = clac_avg_PER(league_avg_stats)

    points = player_stats['PTS']
    fga = player_stats['FGA']
    fta = player_stats['FTA']
    tov = player_stats['TOV']
    reb = player_stats['REB']
    ast = player_stats['AST']
    blk = player_stats['BLK']
    stl = player_stats['STL']
    pf = player_stats['PF']
    min_played = player_stats['MIN']

    missed_fg = (fga - player_stats['FGM'])
    missed_ft = (fta - player_stats['FTM'])

    player_efficiency = (
        points + reb + ast + stl + blk - missed_fg - missed_ft - tov - pf
    )

    return player_efficiency/(player_efficiency_avg * min_played)

# calculate the true shooting precentage
def calculate_ts_pct(player_stats):

    pts = player_stats['PTS']
    fga = player_stats['FGA']
    fta = player_stats['FTA']
    
    ts_pct = pts / (2 * (fga + 0.44 * fta))
    return ts_pct

#calculate assist turnover ratio
def calculate_ast_to_ratio(player_stats):
    ast = player_stats['AST']
    tov = player_stats['TOV']
    
    return ast / tov

#run functions for extra metrics
def extra_player_metrics(df_player, df_leaders):
    df_player["PER_score"] = calc_PER(df_player ,df_leaders)
    df_player["PCT_score"] = calculate_ts_pct(df_player)
    df_player["AST_ratio"]= calculate_ast_to_ratio(df_player)

    return df_player

def home_away_averages(player_df):
    player_df["Home_Average_PTS"] = player_df[player_df['Home'] == 1]['PTS'].mean()
    player_df["Away_Average_PTS"] = player_df[player_df['Home'] == 0]['PTS'].mean()

    player_df["Home_Average_REB"] = player_df[player_df['Home'] == 1]['REB'].mean()
    player_df["Away_Average_REB"] = player_df[player_df['Home'] == 0]['REB'].mean()

    player_df["Home_Average_AST"] = player_df[player_df['Home'] == 1]['AST'].mean()
    player_df["Away_Average_AST"] = player_df[player_df['Home'] == 0]['AST'].mean()

    return player_df

def recent_game_averages(player_df):
    player_df = player_df.copy()
    
    # Reverse the DataFrame to calculate the averages starting from the most recent game
    player_df = player_df[::-1]

    # Points of last # of games
    player_df.loc[:, "Avg_points_last_3"] = player_df["PTS"].rolling(window=3).mean()
    player_df.loc[:, "Avg_points_last_5"] = player_df["PTS"].rolling(window=5).mean()
    player_df.loc[:, "Avg_points_last_7"] = player_df["PTS"].rolling(window=7).mean()

    # Assists of last # of games
    player_df.loc[:, "Avg_Assists_last_3"] = player_df["AST"].rolling(window=3).mean()
    player_df.loc[:, "Avg_Assists_last_5"] = player_df["AST"].rolling(window=5).mean()
    player_df.loc[:, "Avg_Assists_last_7"] = player_df["AST"].rolling(window=7).mean()

    # Rebounds of last # of games
    player_df.loc[:, "Avg_Rebounds_last_3"] = player_df["REB"].rolling(window=3).mean()
    player_df.loc[:, "Avg_Rebounds_last_5"] = player_df["REB"].rolling(window=5).mean()
    player_df.loc[:, "Avg_Rebounds_last_7"] = player_df["REB"].rolling(window=7).mean()

    # Reverse back to original order
    player_df = player_df[::-1]
    
    return player_df



def calc_possesions(team_df, column_name):
    team_df[column_name] = (
    team_df['FGA'] +
    0.44 * team_df['FTA'] -
    team_df['OREB'] +
    team_df['TOV'])

    return team_df

def win_loss_ecoder(df):
    labelEncoder = LabelEncoder()
    df['WL'] = labelEncoder.fit_transform(df['WL'])
    
    return df

def get_player(player_name):
    
    #get specific player data
    player_dict = players.get_players()
    player_stat = [player for player in player_dict if player['full_name'] == player_name][0]
    players_id_stat = player_stat['id']

    #Get current year
    gamelog_player_df = playergamelog.PlayerGameLog(player_id = players_id_stat, season = "2024").get_data_frames()[0]
    gamelog_player_df = pd.DataFrame(gamelog_player_df)

    #get average leaguge data
    leaders = leagueleaders.LeagueLeaders(season='2023-24')
    df_leaders = leaders.get_data_frames()[0]
    df_leaders = pd.DataFrame(df_leaders)

    gamelog_player_df = extra_player_metrics(gamelog_player_df, df_leaders)

    #Encode Wins and loss to binary
    gamelog_player_df = win_loss_ecoder(gamelog_player_df)

    #Regex for home an away binary encoding
    gamelog_player_df["Home"] = gamelog_player_df["MATCHUP"].apply(lambda x: 0 if re.search(r'@', x) else 1)

    gamelog_player_df = home_away_averages(gamelog_player_df)
    gamelog_player_df = recent_game_averages(gamelog_player_df)

    gamelog_player_df["GAME_ID"] = gamelog_player_df["Game_ID"]

    #Drop cols
    gamelog_player_df = gamelog_player_df.drop(columns=["Player_ID", "MATCHUP", "SEASON_ID", "VIDEO_AVAILABLE", "Game_ID"])

    return gamelog_player_df

def combine_games(df):

    agg_functions = {
        'GAME_ID': 'first', 
        'GAME_DATE': 'first', 
        'WL': lambda x: x.loc[x.idxmax()],
        'MIN': 'sum',
        'PTS': 'sum',
        'FGM': 'sum',
        'FGA': 'sum',
        'FG_PCT': lambda x: x.sum() / len(x),
        'FG3M': 'sum',
        'FG3A': 'sum',
        'FG3_PCT': lambda x: x.sum() / len(x),
        'FTM': 'sum',
        'FTA': 'sum',
        'FT_PCT': lambda x: x.sum() / len(x),
        'OREB': 'sum',
        'DREB': 'sum',
        'REB': 'sum',
        'AST': 'sum',
        'STL': 'sum',
        'BLK': 'sum',
        'TOV': 'sum',
        'PF': 'sum',
        'PLUS_MINUS': 'sum',
        'Home': lambda x: x.loc[x.idxmax()],
        'OPP': 'first',
        'SEASON_ID': 'first',
        'TEAM_ID': 'first',
        'TEAM_ABBREVIATION': 'first',
        'TEAM_NAME': 'first',
        'MATCHUP': 'first'
        }
    
    df = df.groupby(df['GAME_ID']).aggregate(agg_functions)

    return df

def get_team(team_name):
    #Get starting team data
    team_dict = teams.get_teams()
    team_stat = [team for team in team_dict if team['full_name'] == team_name][0]
    team_stat_ID = team_stat['id']
    team_stat_games = leaguegamefinder.LeagueGameFinder(team_id_nullable = team_stat_ID).get_data_frames()[0]

    #Filter only the most recent season
    team_stat_games['GAME_DATE'] = pd.to_datetime(team_stat_games['GAME_DATE'], errors='coerce')
    comparison_date = pd.to_datetime("2024-8-21")
    team_stat_games = team_stat_games[team_stat_games["GAME_DATE"] > comparison_date]

    #Encode Wins and loss to binary
    team_stat_games = win_loss_ecoder(team_stat_games)

    #Regex for home an away binary encoding
    team_stat_games["Home"] = team_stat_games["MATCHUP"].apply(lambda x: 0 if re.search(r'@', x) else 1)

    #Regex what team is being played then encode to numeric values
    team_stat_games["OPP"] = team_stat_games["MATCHUP"].str.extract(r'[.@]\s*(\w+)')
    #labelEncoder = LabelEncoder()
    #team_stat_games["OPP"] = labelEncoder.fit_transform(team_stat_games["OPP"])

    team_stat_games = combine_games(team_stat_games)
    team_stat_games = calc_possesions(team_stat_games, "Team_possesions")

    #Drop cols 
    team_stat_games = team_stat_games.drop(columns=["SEASON_ID", "TEAM_ID", "TEAM_ABBREVIATION", "TEAM_NAME", "MATCHUP"])

    return team_stat_games

def calc_usage_pace_offensive_rating(df):
    required_columns = ['FGA', 'FTA', 'TOV', 'MIN_team', 'PTS_team', 'Team_possesions_team', 'OREB']
    for col in required_columns:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")

    df['GAME_DATE'] = pd.to_datetime(df['GAME_DATE'], format='%b %d, %Y')
    df = df.sort_values(by="GAME_DATE", ascending=True)

    # Calculate per-game stats
    df['Player_possessions'] = (
        df['FGA'] - df['OREB'] + df['TOV'] + (0.44 * df['FTA'])
    )

    df['Offensive_Rating'] = (
        (df['PTS'] / df['Player_possessions']) * 100
    ).fillna(0)

    # Handle cases where possessions might be zero or very small
    df['Player_possessions'] = df['Player_possessions'].replace(0, 0.1)
    df['Offensive_Rating'] = df['Offensive_Rating'].replace([float('inf'), -float('inf')], 0)

    # Calculate cumulative averages
    df['Cumulative_Offensive_Rating'] = df['Offensive_Rating'].expanding().mean()

    df['team_possessions'] = (
        df['FGA_team'] - df['OREB_team'] + df['TOV_team'] + (0.44 * df['FTA_team'])
    )

    df['team_off_rating'] = (
        (df['PTS_team']/df['Team_possesions_team']) * 100
    ).fillna(0)

    df['team_possessions'] = df['Team_possesions_team'].replace(0, 0.1)
    df['team_off_rating'] = df['team_off_rating'].replace([float('inf'), -float('inf')], 0)

    # Calculate cumulative averages
    df['Cumulative_team_off_Rating'] = df['team_off_rating'].expanding().mean()

    df['Team_Pace'] = (
        (df['team_possessions'] / (df['MIN_team'] / 5)) * 48
    ).replace([float('inf'), -float('inf')], 0).fillna(0)

    df['Cumulative_Team_Pace'] = df['Team_Pace'].expanding().mean()

    # Calculate Usage Percentage
    df['Cumulative_FGA'] = df['FGA'].cumsum()
    df['Cumulative_FTA'] = df['FTA'].cumsum()
    df['Cumulative_TO'] = df['TOV'].cumsum()
    df['Cumulative_MIN'] = df['MIN_team'].cumsum()
    df['Cumulative_PTS'] = df['PTS_team'].cumsum()

    df['Usage_Percentage'] = (
        100
        * (
            (df['Cumulative_FGA'] + 0.44 * df['Cumulative_FTA'] + df['Cumulative_TO'])
            * df['MIN_team']
        )
        / (df['Cumulative_MIN'] * df['team_possessions'])
    )

    # Drop cumulative columns if not needed for output
    df = df.drop(columns=['Cumulative_FGA', 'Cumulative_FTA', 'Cumulative_TO', 'Cumulative_MIN', 'Cumulative_PTS'])

    return df

def calculate_defensive_rating_up_to_game(main_team_data):
    all_team_def_ratings = []

    #iterate though all the data and obtain the opposing teams data
    for index, row in main_team_data.iterrows():
        opp_name = row['full_opp_name']
        game_date = pd.to_datetime(row['GAME_DATE'], errors='coerce')

        team_dict = teams.get_teams()
        opp_team = [team for team in team_dict if team['full_name'] == opp_name][0]
        opp_team_ID = opp_team['id']
        opp_team_games = leaguegamefinder.LeagueGameFinder(team_id_nullable=opp_team_ID).get_data_frames()[0]

        opp_team_games['GAME_DATE'] = pd.to_datetime(opp_team_games['GAME_DATE'], errors='coerce')
        opp_team_games = opp_team_games[opp_team_games['GAME_DATE'] < game_date]
        
        opp_team_games = calc_possesions(opp_team_games, "opp_possessions")
        opp_team_games['CUMULATIVE_POINTS_ALLOWED'] = opp_team_games['PTS'].cumsum()
        opp_team_games['CUMULATIVE_OPP_POSSESSIONS'] = opp_team_games['opp_possessions'].cumsum()

        #calulate defensive rating doe each team
        if not opp_team_games.empty:
            def_rating = (
                100 * opp_team_games['CUMULATIVE_POINTS_ALLOWED'].iloc[-1] /
                opp_team_games['CUMULATIVE_OPP_POSSESSIONS'].iloc[-1]
            )
        else:
            def_rating = None 

        #only keep what is needed for adding to main data frame
        all_team_def_ratings.append({
            'GAME_ID': row['GAME_ID'],
            'GAME_DATE_player': row['GAME_DATE'],
            'Opp_Team': opp_name,
            'Defensive_Rating': def_rating
        })

    return pd.DataFrame(all_team_def_ratings)

def calculate_opponent_pace_up_to_game(main_team_data):
    all_team_paces = []

    #iterate through the main data obtaining oposing teams data
    for index, row in main_team_data.iterrows():
        opp_name = row['full_opp_name']
        game_date = pd.to_datetime(row['GAME_DATE_player'], errors='coerce')

        team_dict = teams.get_teams()
        opp_team_list = [team for team in team_dict if team['full_name'].strip().lower() == opp_name.strip().lower()]
        opp_team = opp_team_list[0]
        opp_team_ID = opp_team['id']
        opp_team_games = leaguegamefinder.LeagueGameFinder(team_id_nullable=opp_team_ID).get_data_frames()[0]

        opp_team_games['GAME_DATE'] = pd.to_datetime(opp_team_games['GAME_DATE'], errors='coerce')
        opp_team_games = opp_team_games[opp_team_games['GAME_DATE'] < game_date]

        opp_team_games = calc_possesions(opp_team_games, "opp_possessions")

        opp_team_games['GAME_MINUTES'] = 48 

        opp_team_games['CUMULATIVE_OPP_POSSESSIONS'] = opp_team_games['opp_possessions'].cumsum()
        opp_team_games['CUMULATIVE_GAME_MINUTES'] = opp_team_games['GAME_MINUTES'].cumsum()

        #calculate the pace of the opposing team
        if not opp_team_games.empty:
            avg_pace = (
                opp_team_games['CUMULATIVE_OPP_POSSESSIONS'].iloc[-1] *
                48 /
                opp_team_games['CUMULATIVE_GAME_MINUTES'].iloc[-1]
            )
        else:
            avg_pace = None  

        #only keep what is needed for megring the data
        all_team_paces.append({
            'GAME_ID': row['GAME_ID'],
            'GAME_DATE_player': row['GAME_DATE_player'],
            'Opp_Team': opp_name,
            'Opponent_Pace': avg_pace
        })

    return pd.DataFrame(all_team_paces)

nba_teams = {
    "ATL": "Atlanta Hawks",
    "BOS": "Boston Celtics",
    "BKN": "Brooklyn Nets",
    "CHA": "Charlotte Hornets",
    "CHI": "Chicago Bulls",
    "CLE": "Cleveland Cavaliers",
    "DAL": "Dallas Mavericks",
    "DEN": "Denver Nuggets",
    "DET": "Detroit Pistons",
    "GSW": "Golden State Warriors",
    "HOU": "Houston Rockets",
    "IND": "Indiana Pacers",
    "LAC": "Los Angeles Clippers",
    "LAL": "Los Angeles Lakers",
    "MEM": "Memphis Grizzlies",
    "MIA": "Miami Heat",
    "MIL": "Milwaukee Bucks",
    "MIN": "Minnesota Timberwolves",
    "NOP": "New Orleans Pelicans",
    "NYK": "New York Knicks",
    "OKC": "Oklahoma City Thunder",
    "ORL": "Orlando Magic",
    "PHI": "Philadelphia 76ers",
    "PHX": "Phoenix Suns",
    "POR": "Portland Trail Blazers",
    "SAC": "Sacramento Kings",
    "SAS": "San Antonio Spurs",
    "TOR": "Toronto Raptors",
    "UTA": "Utah Jazz",
    "WAS": "Washington Wizards"
}

#in_player = input("What player do you want to bet on? ")
#players_team = input("What team does your player play for? ")
in_player = "LeBron James"
players_team = "Los Angeles Lakers"
opp_team = "New York Knicks"

#opp_team = input("What team is your player playing? ")


player_df = get_player(in_player)
players_team_df = get_team(players_team)
opp_team_df = get_team(opp_team)

players_team_df = players_team_df.rename(columns=lambda col: f"{col}_team")
                                         
players_full_stat = pd.merge(player_df, players_team_df, left_on='GAME_ID', right_index=True, how='inner')
players_full_stat = calc_usage_pace_offensive_rating(players_full_stat)

opp_team_df['full_opp_name'] = [
            nba_teams[team] if team in nba_teams else "Unknown Team"
            for team in opp_team_df["OPP"]
]
opp_team_df_def = calculate_defensive_rating_up_to_game(opp_team_df)

opp_team_df = opp_team_df.reset_index(drop=True)
opp_team_df_def = opp_team_df_def.reset_index(drop=True)

opp_team_df = pd.merge(opp_team_df, opp_team_df_def, on='GAME_ID', how='inner')

opp_team_df_pace = calculate_opponent_pace_up_to_game(opp_team_df)

opp_team_df = pd.merge(opp_team_df, opp_team_df_pace, on='GAME_ID', how='inner')

features_opp = ['Defensive_Rating', 'Opponent_Pace']

important_opp = opp_team_df[features_opp]

features_player = [
    'Avg_points_last_3', 'Avg_points_last_5', 'Avg_points_last_7', 'Usage_Percentage',
    'Home_Average_PTS', 'Away_Average_PTS', 'PCT_score','Cumulative_Offensive_Rating',
    'Cumulative_team_off_Rating'
]

important_player = players_full_stat[features_player]
