class Task:
    def __init__(self, task_id: int, description: str, reward: float):
        self.task_id = task_id
        self.description = description
        self.reward = reward
        self.completed_by = []

tasks = {
    1: Task(1, "Like our Facebook page", 0.01),
    2: Task(2, "Share this post on Twitter", 0.02),
    3: Task(3, "Write a short review", 0.05),
}
