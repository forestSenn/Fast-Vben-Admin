<script lang="ts" setup>
import type { TableColumnsType } from 'ant-design-vue';
import type {
  UserRecord,
  WorkflowDefinitionRecord,
  WorkflowInstanceRecord,
  WorkflowTaskActionPayload,
  WorkflowTaskRecord,
  WorkflowVersionRecord,
} from '#/api';

import { computed, onMounted, reactive, ref } from 'vue';

import { Page } from '@vben/common-ui';
import { IconifyIcon, Plus } from '@vben/icons';

import {
  Button,
  Descriptions,
  DescriptionsItem,
  Form,
  FormItem,
  Input,
  InputNumber,
  message,
  Modal,
  Select,
  Space,
  Table,
  TabPane,
  Tabs,
  Tag,
  Timeline,
  TimelineItem,
} from 'ant-design-vue';

import {
  actOnWorkflowTaskApi,
  createWorkflowDefinitionApi,
  createWorkflowVersionApi,
  listUsersApi,
  listWorkflowDefinitionsApi,
  listWorkflowInstancesApi,
  listWorkflowTasksApi,
  publishWorkflowVersionApi,
  startWorkflowInstanceApi,
  withdrawWorkflowInstanceApi,
} from '#/api';
import { $t } from '#/locales';

const SAMPLE_BPMN = `<definitions xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL" targetNamespace="https://example.test/bpmn">
  <process id="leave_approval" isExecutable="true">
    <startEvent id="start" name="Submit" />
    <userTask id="manager_approval" name="Manager approval" />
    <endEvent id="end" name="Completed" />
    <sequenceFlow id="flow_1" sourceRef="start" targetRef="manager_approval" />
    <sequenceFlow id="flow_2" sourceRef="manager_approval" targetRef="end" />
  </process>
</definitions>`;

const activeTab = ref('tasks');
const loading = ref(false);
const definitions = ref<WorkflowDefinitionRecord[]>([]);
const instances = ref<WorkflowInstanceRecord[]>([]);
const tasks = ref<WorkflowTaskRecord[]>([]);
const users = ref<UserRecord[]>([]);

const taskColumns: TableColumnsType<WorkflowTaskRecord> = [
  { dataIndex: 'name', key: 'name', title: $t('system.workflow.taskName') },
  {
    dataIndex: 'assignment_expression',
    key: 'assignment_expression',
    title: $t('system.workflow.assignment'),
  },
  { dataIndex: 'due_at', key: 'due_at', title: $t('system.workflow.dueAt') },
  { dataIndex: 'status', key: 'status', title: $t('system.workflow.status') },
  { key: 'operation', title: $t('system.workflow.operation'), width: 120 },
];

const instanceColumns: TableColumnsType<WorkflowInstanceRecord> = [
  {
    dataIndex: 'title',
    key: 'title',
    title: $t('system.workflow.instanceTitle'),
  },
  {
    dataIndex: 'business_type',
    key: 'business_type',
    title: $t('system.workflow.businessType'),
  },
  {
    dataIndex: 'business_id',
    key: 'business_id',
    title: $t('system.workflow.businessId'),
  },
  { dataIndex: 'status', key: 'status', title: $t('system.workflow.status') },
  {
    dataIndex: 'created_at',
    key: 'created_at',
    title: $t('system.workflow.createdAt'),
  },
  { key: 'operation', title: $t('system.workflow.operation'), width: 120 },
];

const definitionColumns: TableColumnsType<WorkflowDefinitionRecord> = [
  { dataIndex: 'name', key: 'name', title: $t('system.workflow.name') },
  { dataIndex: 'code', key: 'code', title: $t('system.workflow.code') },
  {
    key: 'versions',
    title: $t('system.workflow.version'),
    width: 300,
  },
  { key: 'operation', title: $t('system.workflow.operation'), width: 150 },
];

function formatDate(value?: null | string) {
  return value ? new Date(value).toLocaleString() : '-';
}

function statusColor(status: string) {
  if (['approved', 'completed', 'published'].includes(status)) return 'success';
  if (['rejected', 'withdrawn'].includes(status)) return 'error';
  if (status === 'retired') return 'default';
  return 'processing';
}

function statusText(status: string) {
  const key = `system.workflow.${status}`;
  const translated = $t(key);
  return translated === key ? status : translated;
}

async function refresh() {
  loading.value = true;
  try {
    [definitions.value, instances.value, tasks.value] = await Promise.all([
      listWorkflowDefinitionsApi(),
      listWorkflowInstancesApi(),
      listWorkflowTasksApi(),
    ]);
  } finally {
    loading.value = false;
  }
}

function parseJson<T>(value: string, fallback: T): T {
  if (!value.trim()) return fallback;
  try {
    return JSON.parse(value) as T;
  } catch {
    message.error($t('system.workflow.invalidJson'));
    throw new Error('Invalid JSON');
  }
}

const definitionModalOpen = ref(false);
const editingDefinitionId = ref<string>();
const definitionSaving = ref(false);
const definitionForm = reactive({
  assignments: '{\n  "manager_approval": "starter"\n}',
  bpmnXml: SAMPLE_BPMN,
  code: '',
  description: '',
  name: '',
  processId: 'leave_approval',
  timeoutHours: 24 as number | undefined,
});

function openDefinitionModal(definition?: WorkflowDefinitionRecord) {
  editingDefinitionId.value = definition?.id;
  definitionForm.code = definition?.code ?? '';
  definitionForm.name = definition?.name ?? '';
  definitionForm.description = definition?.description ?? '';
  definitionForm.processId = 'leave_approval';
  definitionForm.bpmnXml = SAMPLE_BPMN;
  definitionForm.assignments = '{\n  "manager_approval": "starter"\n}';
  definitionForm.timeoutHours = 24;
  definitionModalOpen.value = true;
}

async function saveDefinition() {
  if (
    !definitionForm.processId.trim() ||
    !definitionForm.bpmnXml.trim() ||
    (!editingDefinitionId.value &&
      (!definitionForm.code.trim() || !definitionForm.name.trim()))
  ) {
    return;
  }
  const taskAssignments = parseJson<Record<string, string>>(
    definitionForm.assignments,
    {},
  );
  definitionSaving.value = true;
  try {
    const versionPayload = {
      bpmn_xml: definitionForm.bpmnXml,
      process_id: definitionForm.processId,
      task_assignments: taskAssignments,
      timeout_hours: definitionForm.timeoutHours,
    };
    await (editingDefinitionId.value
      ? createWorkflowVersionApi(editingDefinitionId.value, versionPayload)
      : createWorkflowDefinitionApi({
          ...versionPayload,
          code: definitionForm.code,
          description: definitionForm.description || null,
          name: definitionForm.name,
        }));
    definitionModalOpen.value = false;
    message.success($t('system.workflow.success'));
    await refresh();
  } finally {
    definitionSaving.value = false;
  }
}

async function publishVersion(version: WorkflowVersionRecord) {
  await publishWorkflowVersionApi(version.id);
  message.success($t('system.workflow.success'));
  await refresh();
}

const publishedDefinitions = computed(() =>
  definitions.value.filter((definition) =>
    definition.versions?.some((version) => version.status === 'published'),
  ),
);

const startModalOpen = ref(false);
const startSaving = ref(false);
const startForm = reactive({
  businessId: '',
  businessType: '',
  definitionCode: '',
  formData: '{}',
  title: '',
});

function openStartModal() {
  startForm.definitionCode = publishedDefinitions.value[0]?.code ?? '';
  startForm.title = '';
  startForm.businessType = '';
  startForm.businessId = '';
  startForm.formData = '{}';
  startModalOpen.value = true;
}

async function startInstance() {
  if (!startForm.definitionCode || !startForm.title.trim()) return;
  const formData = parseJson<Record<string, unknown>>(startForm.formData, {});
  startSaving.value = true;
  try {
    await startWorkflowInstanceApi({
      business_id: startForm.businessId || null,
      business_type: startForm.businessType || null,
      definition_code: startForm.definitionCode,
      form_data: formData,
      title: startForm.title,
    });
    startModalOpen.value = false;
    activeTab.value = 'tasks';
    message.success($t('system.workflow.success'));
    await refresh();
  } finally {
    startSaving.value = false;
  }
}

const actionModalOpen = ref(false);
const actionSaving = ref(false);
const selectedTask = ref<WorkflowTaskRecord>();
const actionForm = reactive<{
  action: WorkflowTaskActionPayload['action'];
  comment: string;
  targetUserId?: string;
}>({ action: 'approve', comment: '', targetUserId: undefined });

async function openActionModal(task: WorkflowTaskRecord) {
  selectedTask.value = task;
  actionForm.action = 'approve';
  actionForm.comment = '';
  actionForm.targetUserId = undefined;
  actionModalOpen.value = true;
  if (users.value.length === 0) {
    const result = await listUsersApi({ page: 1, page_size: 100 });
    users.value = result.items;
  }
}

function openActionModalFromRow(record: unknown) {
  return openActionModal(record as WorkflowTaskRecord);
}

const actionNeedsUser = computed(() =>
  ['cc', 'transfer'].includes(actionForm.action),
);

async function submitAction() {
  if (!selectedTask.value) return;
  if (actionNeedsUser.value && !actionForm.targetUserId) return;
  actionSaving.value = true;
  try {
    await actOnWorkflowTaskApi(selectedTask.value.id, {
      action: actionForm.action,
      comment: actionForm.comment || null,
      target_user_id: actionForm.targetUserId || null,
    });
    actionModalOpen.value = false;
    message.success($t('system.workflow.success'));
    await refresh();
  } finally {
    actionSaving.value = false;
  }
}

async function withdrawInstance(instance: WorkflowInstanceRecord) {
  await withdrawWorkflowInstanceApi(instance.id);
  message.success($t('system.workflow.success'));
  await refresh();
}

function withdrawInstanceFromRow(record: unknown) {
  return withdrawInstance(record as WorkflowInstanceRecord);
}

function openDefinitionModalFromRow(record: unknown) {
  openDefinitionModal(record as WorkflowDefinitionRecord);
}

onMounted(refresh);
</script>

<template>
  <Page :title="$t('system.workflow.title')" auto-content-height>
    <div class="flex h-full flex-col bg-background px-4 py-3">
      <div class="mb-3 flex flex-wrap items-center justify-between gap-2">
        <Tabs v-model:active-key="activeTab" class="workflow-tabs flex-1">
          <TabPane key="tasks" :tab="$t('system.workflow.tasks')" />
          <TabPane key="instances" :tab="$t('system.workflow.instances')" />
          <TabPane key="definitions" :tab="$t('system.workflow.definitions')" />
        </Tabs>
        <Space wrap>
          <Button :loading="loading" @click="refresh">
            <IconifyIcon icon="lucide:refresh-cw" />
            {{ $t('system.workflow.refresh') }}
          </Button>
          <Button
            v-access:code="'workflow:instance:start'"
            type="primary"
            :disabled="publishedDefinitions.length === 0"
            @click="openStartModal"
          >
            <Plus class="size-5" />
            {{ $t('system.workflow.start') }}
          </Button>
          <Button
            v-if="activeTab === 'definitions'"
            v-access:code="'workflow:definition:manage'"
            @click="openDefinitionModal()"
          >
            <Plus class="size-5" />
            {{ $t('system.workflow.createDefinition') }}
          </Button>
        </Space>
      </div>

      <Table
        v-if="activeTab === 'tasks'"
        :columns="taskColumns"
        :data-source="tasks"
        :loading="loading"
        row-key="id"
        :pagination="{ pageSize: 20 }"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'due_at'">
            <Space>
              <span>{{ formatDate(record.due_at) }}</span>
              <Tag v-if="record.is_overdue" color="error">
                {{ $t('system.workflow.overdue') }}
              </Tag>
            </Space>
          </template>
          <Tag
            v-else-if="column.key === 'status'"
            :color="statusColor(record.status)"
          >
            {{ statusText(record.status) }}
          </Tag>
          <Button
            v-else-if="column.key === 'operation'"
            type="link"
            @click="openActionModalFromRow(record)"
          >
            {{ $t('system.workflow.action') }}
          </Button>
        </template>
      </Table>

      <Table
        v-else-if="activeTab === 'instances'"
        :columns="instanceColumns"
        :data-source="instances"
        :loading="loading"
        row-key="id"
        :pagination="{ pageSize: 20 }"
      >
        <template #bodyCell="{ column, record }">
          <Tag
            v-if="column.key === 'status'"
            :color="statusColor(record.status)"
          >
            {{ statusText(record.status) }}
          </Tag>
          <span v-else-if="column.key === 'created_at'">
            {{ formatDate(record.created_at) }}
          </span>
          <Button
            v-else-if="
              column.key === 'operation' && record.status === 'running'
            "
            danger
            type="link"
            @click="withdrawInstanceFromRow(record)"
          >
            {{ $t('system.workflow.withdraw') }}
          </Button>
        </template>
        <template #expandedRowRender="{ record }">
          <Descriptions bordered size="small" :column="2">
            <DescriptionsItem :label="$t('system.workflow.formData')" :span="2">
              <pre class="m-0 whitespace-pre-wrap">{{
                JSON.stringify(record.form_data, null, 2)
              }}</pre>
            </DescriptionsItem>
          </Descriptions>
          <div class="mt-4 font-medium">{{ $t('system.workflow.audit') }}</div>
          <Timeline class="mt-3">
            <TimelineItem v-for="audit in record.audits" :key="audit.id">
              <strong>{{ statusText(audit.action) }}</strong>
              <span class="ml-2 text-muted-foreground">{{
                formatDate(audit.created_at)
              }}</span>
              <div v-if="audit.comment">{{ audit.comment }}</div>
            </TimelineItem>
          </Timeline>
        </template>
      </Table>

      <Table
        v-else
        :columns="definitionColumns"
        :data-source="definitions"
        :loading="loading"
        row-key="id"
        :pagination="false"
      >
        <template #bodyCell="{ column, record }">
          <Space v-if="column.key === 'versions'" wrap>
            <Tag
              v-for="version in record.versions"
              :key="version.id"
              :color="statusColor(version.status)"
            >
              v{{ version.version }} · {{ statusText(version.status) }}
              <Button
                v-if="version.status === 'draft'"
                class="ml-1 px-0"
                size="small"
                type="link"
                @click="publishVersion(version)"
              >
                {{ $t('system.workflow.publish') }}
              </Button>
            </Tag>
          </Space>
          <Button
            v-else-if="column.key === 'operation'"
            type="link"
            @click="openDefinitionModalFromRow(record)"
          >
            {{ $t('system.workflow.createVersion') }}
          </Button>
        </template>
      </Table>
    </div>

    <Modal
      v-model:open="definitionModalOpen"
      :confirm-loading="definitionSaving"
      :title="
        editingDefinitionId
          ? $t('system.workflow.createVersion')
          : $t('system.workflow.createDefinition')
      "
      width="760px"
      @ok="saveDefinition"
    >
      <Form layout="vertical">
        <div
          v-if="!editingDefinitionId"
          class="grid grid-cols-1 gap-x-4 sm:grid-cols-2"
        >
          <FormItem :label="$t('system.workflow.code')" required>
            <Input v-model:value="definitionForm.code" />
          </FormItem>
          <FormItem :label="$t('system.workflow.name')" required>
            <Input v-model:value="definitionForm.name" />
          </FormItem>
        </div>
        <FormItem
          v-if="!editingDefinitionId"
          :label="$t('system.workflow.description')"
        >
          <Input v-model:value="definitionForm.description" />
        </FormItem>
        <div class="grid grid-cols-1 gap-x-4 sm:grid-cols-2">
          <FormItem :label="$t('system.workflow.processId')" required>
            <Input v-model:value="definitionForm.processId" />
          </FormItem>
          <FormItem :label="$t('system.workflow.timeoutHours')">
            <InputNumber
              v-model:value="definitionForm.timeoutHours"
              class="w-full"
              :min="1"
            />
          </FormItem>
        </div>
        <FormItem :label="$t('system.workflow.assignments')">
          <Input.TextArea
            v-model:value="definitionForm.assignments"
            :rows="4"
          />
        </FormItem>
        <FormItem :label="$t('system.workflow.bpmnXml')" required>
          <Input.TextArea v-model:value="definitionForm.bpmnXml" :rows="12" />
        </FormItem>
      </Form>
    </Modal>

    <Modal
      v-model:open="startModalOpen"
      :confirm-loading="startSaving"
      :title="$t('system.workflow.start')"
      @ok="startInstance"
    >
      <Form layout="vertical">
        <FormItem :label="$t('system.workflow.definitions')" required>
          <Select
            v-model:value="startForm.definitionCode"
            :options="
              publishedDefinitions.map((item) => ({
                label: item.name,
                value: item.code,
              }))
            "
          />
        </FormItem>
        <FormItem :label="$t('system.workflow.instanceTitle')" required>
          <Input v-model:value="startForm.title" />
        </FormItem>
        <div class="grid grid-cols-1 gap-x-4 sm:grid-cols-2">
          <FormItem :label="$t('system.workflow.businessType')">
            <Input v-model:value="startForm.businessType" />
          </FormItem>
          <FormItem :label="$t('system.workflow.businessId')">
            <Input v-model:value="startForm.businessId" />
          </FormItem>
        </div>
        <FormItem :label="$t('system.workflow.formData')">
          <Input.TextArea v-model:value="startForm.formData" :rows="6" />
        </FormItem>
      </Form>
    </Modal>

    <Modal
      v-model:open="actionModalOpen"
      :confirm-loading="actionSaving"
      :title="$t('system.workflow.action')"
      @ok="submitAction"
    >
      <Form layout="vertical">
        <FormItem :label="$t('system.workflow.action')" required>
          <Select
            v-model:value="actionForm.action"
            :options="[
              { label: $t('system.workflow.approve'), value: 'approve' },
              { label: $t('system.workflow.reject'), value: 'reject' },
              { label: $t('system.workflow.transfer'), value: 'transfer' },
              { label: $t('system.workflow.cc'), value: 'cc' },
            ]"
          />
        </FormItem>
        <FormItem
          v-if="actionNeedsUser"
          :label="$t('system.workflow.targetUser')"
          required
        >
          <Select
            v-model:value="actionForm.targetUserId"
            show-search
            option-filter-prop="label"
            :options="
              users.map((user) => ({
                label: user.full_name
                  ? `${user.full_name} (${user.email})`
                  : user.email,
                value: user.id,
              }))
            "
          />
        </FormItem>
        <FormItem :label="$t('system.workflow.comment')">
          <Input.TextArea v-model:value="actionForm.comment" :rows="4" />
        </FormItem>
      </Form>
    </Modal>
  </Page>
</template>

<style scoped>
.workflow-tabs :deep(.ant-tabs-nav) {
  margin-bottom: 0;
}
</style>
