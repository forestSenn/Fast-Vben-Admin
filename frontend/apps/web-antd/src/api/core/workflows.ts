import type {
  WorkflowDefinitionCreate,
  WorkflowDefinitionPublic,
  WorkflowInstancePublic,
  WorkflowStartRequest,
  WorkflowTaskActionRequest,
  WorkflowTaskPublic,
  WorkflowVersionCreate,
  WorkflowVersionPublic,
} from '#/api/generated';

import { requestClient } from '#/api/request';

export type WorkflowDefinitionRecord = WorkflowDefinitionPublic;
export type WorkflowInstanceRecord = WorkflowInstancePublic;
export type WorkflowTaskRecord = WorkflowTaskPublic;
export type WorkflowVersionRecord = WorkflowVersionPublic;
export type WorkflowDefinitionPayload = WorkflowDefinitionCreate;
export type WorkflowVersionPayload = WorkflowVersionCreate;
export type WorkflowStartPayload = WorkflowStartRequest;
export type WorkflowTaskActionPayload = WorkflowTaskActionRequest;

export function listWorkflowDefinitionsApi() {
  return requestClient.get<WorkflowDefinitionRecord[]>(
    '/workflows/definitions',
  );
}

export function createWorkflowDefinitionApi(data: WorkflowDefinitionPayload) {
  return requestClient.post<WorkflowDefinitionRecord>(
    '/workflows/definitions',
    data,
  );
}

export function createWorkflowVersionApi(
  definitionId: string,
  data: WorkflowVersionPayload,
) {
  return requestClient.post<WorkflowVersionRecord>(
    `/workflows/definitions/${definitionId}/versions`,
    data,
  );
}

export function publishWorkflowVersionApi(versionId: string) {
  return requestClient.post<WorkflowVersionRecord>(
    `/workflows/versions/${versionId}/publish`,
  );
}

export function listWorkflowInstancesApi() {
  return requestClient.get<WorkflowInstanceRecord[]>('/workflows/instances');
}

export function startWorkflowInstanceApi(data: WorkflowStartPayload) {
  return requestClient.post<WorkflowInstanceRecord>(
    '/workflows/instances',
    data,
  );
}

export function withdrawWorkflowInstanceApi(instanceId: string) {
  return requestClient.post<WorkflowInstanceRecord>(
    `/workflows/instances/${instanceId}/withdraw`,
  );
}

export function listWorkflowTasksApi(overdue?: boolean) {
  return requestClient.get<WorkflowTaskRecord[]>('/workflows/tasks', {
    params: { overdue },
  });
}

export function actOnWorkflowTaskApi(
  taskId: string,
  data: WorkflowTaskActionPayload,
) {
  return requestClient.post<WorkflowInstanceRecord>(
    `/workflows/tasks/${taskId}/actions`,
    data,
  );
}
