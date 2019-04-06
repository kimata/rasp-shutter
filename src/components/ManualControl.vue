<template>
<div class="row mb-4">
  <div class="col-xl-6 offset-xl-3 col-lg-8 offset-lg-2 col-md-10 offset-md-1">
    <h2>手動</h2>
    <div class="container mt-4">
      <button class="btn btn-success col-5"
              @click="control('open')">▲ 上げる
      </button><button class="btn btn-success col-5 offset-2"
                       @click="control('close')">▼下げる
      </button>
    </div>
  </div>
</div>

</template>

<script>
import axios from 'axios'
import AppConfig from '../mixins/AppConfig.js'

export default {
  name: 'manual-control',
  mixins: [ AppConfig ],
  methods: {
    control: function (mode) {
      axios
        .get(this.AppConfig['apiEndpoint'] + 'shutter_ctrl', {
          params: { set: mode }
        })
        .then(response => {
          if (response.data.result) {
            this.$root.$toastr.success('正常に制御できました．', '成功')
          } else {
            this.$root.$toastr.error('制御に失敗しました．', 'エラー')
          }
        })
        .catch(_ => {
          this.$root.$toastr.error('制御に失敗しました．', 'エラー')
        })
      this.$eventHub.$emit('manual-control')
    }
  }
}
</script>

<style scoped>
</style>
