<template>
  <main class="walkthrough">
    <header>
      <p class="eyebrow">MUXTRAIL ARCHITECTURE</p>
      <h1>Follow one assistant turn from channel event to channel reply</h1>
      <p>
        MuxTrail runs WebChat, Slack, Discord, and optional Feishu traffic through the same
        gateway, session store, model runtime, tool registry, and trace stream.
      </p>
    </header>

    <ol aria-label="MuxTrail request flow">
      <li v-for="step in steps" :key="step.title">
        <span>{{ step.number }}</span>
        <div>
          <h2>{{ step.title }}</h2>
          <p>{{ step.detail }}</p>
          <code>{{ step.artifact }}</code>
        </div>
      </li>
    </ol>
  </main>
</template>

<script setup lang="ts">
const steps = [
  {
    number: '01',
    title: 'Channel adapter normalizes the event',
    detail: 'Bot messages and retries are filtered before a normalized inbound message is emitted.',
    artifact: 'InboundMessage(channel, accountId, workspaceId, senderId, conversationId, threadId)',
  },
  {
    number: '02',
    title: 'Gateway assigns a trace and session',
    detail: 'Stable keys isolate channels, workspaces, conversations, threads, and users.',
    artifact: 'traceId → sessionKey → transcript',
  },
  {
    number: '03',
    title: 'Runtime calls the configured model',
    detail: 'The model receives the system prompt, active-session history, and current user turn.',
    artifact: 'AgentRunRequest → provider stream',
  },
  {
    number: '04',
    title: 'Allowed tools execute as structured actions',
    detail: 'Arguments are validated, execution is bounded, and results return to model context.',
    artifact: 'tool call → policy → handler → tool result → model',
  },
  {
    number: '05',
    title: 'The originating channel receives the final answer',
    detail: 'Delivery metadata and failures are attached to the same observable trace.',
    artifact: 'OutboundMessage → DeliveryResult',
  },
]
</script>

<style scoped>
.walkthrough { max-width: 980px; margin: 0 auto; padding: 48px 24px; font-family: Inter, sans-serif; color: #172033; }
header { max-width: 760px; margin-bottom: 40px; }
.eyebrow { color: #2457ff; font: 700 12px/1 monospace; letter-spacing: .12em; }
h1 { font-size: clamp(32px, 5vw, 58px); line-height: 1.02; margin: 12px 0 20px; }
header p { color: #566078; font-size: 18px; line-height: 1.6; }
ol { list-style: none; padding: 0; display: grid; gap: 14px; }
li { display: grid; grid-template-columns: 56px 1fr; gap: 18px; padding: 22px; border: 1px solid #d9dfeb; background: #fff; }
li > span { color: #2457ff; font: 700 14px/1 monospace; }
h2 { margin: 0 0 8px; font-size: 20px; }
li p { margin: 0 0 12px; color: #566078; line-height: 1.5; }
code { display: block; overflow-wrap: anywhere; color: #243250; }
</style>
