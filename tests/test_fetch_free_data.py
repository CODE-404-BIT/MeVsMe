from pathlib import Path

from betmodel.providers.football_data_uk import latest_fixtures_url, season_csv_url


def test_latest_fixture_url_is_public_csv():
    assert latest_fixtures_url() == "https://www.football-data.co.uk/matches/resources/fixtures.csv"


def test_season_csv_url_uses_free_archive_pattern():
    assert season_csv_url("2627", "E0") == "https://www.football-data.co.uk/mmz4281/2627/E0.csv"
