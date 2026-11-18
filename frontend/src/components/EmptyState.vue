<script setup lang="ts">
defineProps<{
  title: string
  description: string
}>()
</script>

<template>
  <section class="empty-panel" role="status">
    <h2>{{ title }}</h2>
    <p>{{ description }}</p>
  </section>
</template>
