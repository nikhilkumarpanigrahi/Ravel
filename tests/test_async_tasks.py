import time

from ravel.application.task_runner import TaskRunner, TaskStatus


def test_task_runner_lifecycle():
    runner = TaskRunner()

    def sample_job(x, y):
        time.sleep(0.05)
        return x + y

    task = runner.submit("Addition", sample_job, 10, 20)
    assert task.task_id.startswith("TASK-")
    assert task.status in (TaskStatus.PENDING, TaskStatus.RUNNING)

    # Wait for completion
    time.sleep(0.1)
    retrieved = runner.get(task.task_id)
    assert retrieved is not None
    assert retrieved.status == TaskStatus.COMPLETED
    assert retrieved.result == 30
    assert retrieved.error is None
    assert retrieved.to_dict()["status"] == "COMPLETED"


def test_task_runner_error_handling():
    runner = TaskRunner()

    def failing_job():
        raise ValueError("Simulated pipeline failure")

    task = runner.submit("Failing", failing_job)
    time.sleep(0.1)

    retrieved = runner.get(task.task_id)
    assert retrieved.status == TaskStatus.FAILED
    assert "Simulated pipeline failure" in (retrieved.error or "")
