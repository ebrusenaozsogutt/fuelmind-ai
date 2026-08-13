"""Read-only readiness summary for the Stage 8.9 manual demo."""

from sqlalchemy import text

from app.database import engine


def main() -> None:
    with engine.connect() as connection:
        models = connection.execute(
            text("SELECT model_family, version, is_active FROM model_versions ORDER BY id")
        ).all()
        stations = connection.execute(
            text("SELECT id, code FROM stations ORDER BY id")
        ).all()
        runs = connection.execute(
            text(
                "SELECT id, station_id, status, mode "
                "FROM simulation_runs ORDER BY id DESC LIMIT 5"
            )
        ).all()
        users = connection.execute(
            text("SELECT username, role, is_active FROM users ORDER BY id")
        ).all()
        equipment = connection.execute(
            text("SELECT id, station_id, code FROM pumps ORDER BY id")
        ).all()
        pump_four_history = connection.execute(
            text(
                "SELECT simulation_run_id, COUNT(*), MIN(reading_timestamp), MAX(reading_timestamp) "
                "FROM sensor_readings WHERE pump_id = 4 GROUP BY simulation_run_id "
                "ORDER BY (MAX(reading_timestamp) - MIN(reading_timestamp)) DESC LIMIT 5"
            )
        ).all()
        active_history = connection.execute(
            text(
                "SELECT pump_id, simulation_run_id, MAX(flow_rate) "
                "FROM sensor_readings WHERE flow_rate > 0 GROUP BY pump_id, simulation_run_id "
                "ORDER BY COUNT(*) DESC LIMIT 10"
            )
        ).all()
        run_thirteen_scenarios = connection.execute(
            text(
                "SELECT scenario_type, target_type, target_id, start_time, duration_minutes "
                "FROM simulation_scenarios WHERE simulation_run_id = 13 ORDER BY start_time"
            )
        ).all()
    print(f"models={models}")
    print(f"stations={stations}")
    print(f"recent_runs={runs}")
    print(f"users={users}")
    print(f"pumps={equipment}")
    print(f"pump_4_history={pump_four_history}")
    print(f"active_pump_history={active_history}")
    print(f"run_13_scenarios={run_thirteen_scenarios}")


if __name__ == "__main__":
    main()
