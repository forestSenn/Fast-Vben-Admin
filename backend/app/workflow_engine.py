import uuid
from dataclasses import dataclass

from SpiffWorkflow.bpmn.parser.BpmnParser import BpmnParser
from SpiffWorkflow.bpmn.serializer.workflow import BpmnWorkflowSerializer
from SpiffWorkflow.bpmn.workflow import BpmnWorkflow
from SpiffWorkflow.task import TaskState


@dataclass(frozen=True)
class ReadyWorkflowTask:
    engine_task_id: str
    task_key: str
    name: str


def parse_workflow_spec(*, bpmn_xml: str, process_id: str):
    parser = BpmnParser()
    parser.add_bpmn_str(bpmn_xml.encode())
    return parser.get_spec(process_id)


def validate_workflow_definition(*, bpmn_xml: str, process_id: str) -> None:
    parse_workflow_spec(bpmn_xml=bpmn_xml, process_id=process_id)


def start_workflow(
    *, bpmn_xml: str, process_id: str
) -> tuple[str, list[ReadyWorkflowTask], bool]:
    workflow = BpmnWorkflow(
        parse_workflow_spec(bpmn_xml=bpmn_xml, process_id=process_id)
    )
    workflow.run_all()
    return _serialize_result(workflow)


def complete_workflow_task(
    *, engine_state: str, engine_task_id: str
) -> tuple[str, list[ReadyWorkflowTask], bool]:
    serializer = BpmnWorkflowSerializer()
    workflow = serializer.deserialize_json(engine_state)
    task = workflow.get_task_from_id(uuid.UUID(engine_task_id))
    if task is None or not task.has_state(TaskState.READY):
        raise ValueError("Workflow task is not ready")
    task.complete()
    workflow.run_all()
    return _serialize_result(workflow)


def _serialize_result(
    workflow: BpmnWorkflow,
) -> tuple[str, list[ReadyWorkflowTask], bool]:
    ready_tasks = [
        ReadyWorkflowTask(
            engine_task_id=str(task.id),
            task_key=task.task_spec.bpmn_id,
            name=task.task_spec.bpmn_name or task.task_spec.bpmn_id,
        )
        for task in workflow.get_tasks(state=TaskState.READY)
    ]
    engine_state = BpmnWorkflowSerializer().serialize_json(workflow)
    return engine_state, ready_tasks, workflow.is_completed()
