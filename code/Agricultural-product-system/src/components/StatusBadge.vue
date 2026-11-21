<script setup>
import { labels } from '@/stores/workspace'
defineProps({ value: String })
</script>
<template>
  <span class="status-badge" :class="value"><i></i>{{ labels[value] || value || '未记录' }}</span>
</template>
