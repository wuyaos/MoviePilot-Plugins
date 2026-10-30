<script setup>
defineProps({
  title: { type: String, required: true },
  icon: { type: String, default: '' },
})
</script>

<template>
  <section class="dm-form-section" :aria-label="title">
    <header class="dm-form-section-heading">
      <VIcon v-if="icon" :icon="icon" size="18" class="dm-form-section-icon" aria-hidden="true" />
      <h3 class="dm-form-section-title">{{ title }}</h3>
      <VDivider class="dm-form-section-line" aria-hidden="true" />
      <div v-if="$slots.actions" class="dm-form-section-actions"><slot name="actions" /></div>
    </header>
    <div class="dm-form-section-content"><slot /></div>
  </section>
</template>

<style scoped>
.dm-form-section { min-width: 0; container-type: inline-size; }
.dm-form-section + .dm-form-section { margin-top: 20px; }
.dm-form-section-heading { display: flex; align-items: center; gap: 12px; min-width: 0; margin-bottom: 12px; }
.dm-form-section-icon { flex: 0 0 auto; color: var(--dm-color-secondary); }
.dm-form-section-title { flex: 0 1 auto; min-width: 0; margin: 0; overflow-wrap: anywhere; font-size: 14px; font-weight: 500; line-height: 20px; color: rgb(var(--v-theme-on-surface)); }
.dm-form-section-line { flex: 1 1 24px; min-width: 0; align-self: center; }
.dm-form-section-actions { flex: 0 0 auto; display: flex; align-items: center; gap: 8px; }
.dm-form-section-content { min-width: 0; }
@container (max-width: 340px) {
  .dm-form-section-heading { flex-wrap: wrap; gap: 8px; }
  .dm-form-section-line { display: none; }
  .dm-form-section-actions { margin-inline-start: auto; max-width: 100%; flex-wrap: wrap; }
}
</style>
