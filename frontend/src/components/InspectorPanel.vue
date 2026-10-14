<template>
  <aside class="inspector">
    <div class="summary">
      <p class="eyebrow">INSPECTOR</p>
      <h2>{{ statusLabel(runtime.activeRun?.status || 'idle') }}</h2>
      <div class="facts">
        <span>{{ runtime.activeRun?.provider || '-' }}</span>
        <span>{{ runtime.activeRun?.model || '-' }}</span>
      </div>
      <dl v-if="runtime.activeRun" class="trace-facts">
        <template v-for="fact in traceFacts" :key="fact.label">
          <dt>{{ fact.label }}</dt><dd>{{ fact.value }}</dd>
        </template>
      </dl>
    </div>

    <div class="output">
      <div class="output-head">
        <span>Final response / visible output</span>
        <strong>{{ runtime.activeRun?.output.length || 0 }}</strong>
      </div>
      <div class="rendered-output">
        <SafeMarkdown :text="runtime.activeRun?.output || 'No model output yet.'" />
      </div>
    </div>

    <ToolCallPanel />
    <MessageContextPanel />
  </aside>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import MessageContextPanel from '@/components/MessageContextPanel.vue'
import SafeMarkdown from '@/components/SafeMarkdown.vue'
import ToolCallPanel from '@/components/ToolCallPanel.vue'
import { useRuntimeStore } from '@/stores/runtime'

const runtime = useRuntimeStore()
const traceFacts = computed(() => {
  const run = runtime.activeRun
  if (!run) return []
  return [
    ['Channel', run.channel],
    ['Account', run.accountId],
    ['Workspace / server', run.workspaceId],
    ['Safe user', run.userId],
    ['Conversation', run.conversationId],
    ['Thread', run.threadId],
    ['Session key', run.sessionKey],
    ['Session ID', run.sessionId],
    ['Trace ID', run.traceId || run.id],
    ['Provider', run.provider],
    ['Model', run.model],
    ['Overall latency', run.runtimeMs ? `${run.runtimeMs} ms` : ''],
    ['Error', run.error],
  ].filter((item) => item[1]).map(([label, value]) => ({ label, value }))
})

function statusLabel(status: string) {
  const labels: Record<string, string> = {
    idle: 'Idle',
    active: 'Running',
    done: 'Complete',
    failed: 'Failed',
  }
  return labels[status] || status
}
</script>

<style scoped>
.inspector {
  border-left: 1px solid var(--border);
  background: rgba(255, 255, 255, 0.78);
  min-width: 390px;
  height: 100%;
  max-height: 100%;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow-x: hidden;
  overflow-y: auto;
  overscroll-behavior: contain;
  scrollbar-gutter: stable;
}
.summary {
  padding: 20px;
  border-bottom: 1px solid var(--border);
  background: #fff;
}
.eyebrow {
  font: 700 10px/1 var(--mono);
  color: var(--accent);
  margin-bottom: 6px;
}
h2 {
  font-size: 28px;
  text-transform: uppercase;
}
.facts {
  margin-top: 10px;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.facts span {
  border: 1px solid var(--border);
  padding: 5px 8px;
  color: var(--muted);
  font: 700 10px/1 var(--mono);
}
.trace-facts {
  display: grid;
  grid-template-columns: 112px minmax(0, 1fr);
  gap: 6px 10px;
  margin: 14px 0 0;
  font: 600 10px/1.4 var(--mono);
}
.trace-facts dt { color: var(--muted); }
.trace-facts dd { margin: 0; overflow-wrap: anywhere; }
.output {
  border-bottom: 1px solid var(--border);
}
.output-head {
  display: flex;
  justify-content: space-between;
  padding: 11px 14px;
  color: var(--muted);
  font: 700 10px/1 var(--mono);
  border-bottom: 1px solid var(--border);
}
.rendered-output {
  margin: 0;
  padding: 14px;
  overflow-wrap: anywhere;
  font: 500 12px/1.6 var(--mono);
  color: #111827;
  background: #f9fafb;
}
@media (max-width: 960px) {
  .inspector {
    min-width: 0;
    border-left: 0;
    border-top: 1px solid var(--border);
  }
}
</style>
