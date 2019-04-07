<template>
<div class="row mb-4">
  <div class="col-xl-6 offset-xl-3 col-lg-8 offset-lg-2 col-md-10 offset-md-1">
    <h2>実行ログ</h2>
    <div class="container">
      <p v-if="log.length == 0">ログがありません。</p>
      <div v-else class="row mb-2" v-for="entry in log.slice((page-1)*pageSize, page*pageSize)">
        <div class="col-12 font-weight-bold">
          {{entry.date}}
          <small class="text-muted">({{entry.fromNow}})</small>
        </div>
        <div class="col-12" v-html="entry.message.replace(/\n/g,'<br/>')"></div>
      </div>
      <b-pagination
        v-model="page"
        :total-rows="log.length"
        :per-page="pageSize"
        class="justify-content-center"
        ></b-pagination>
    </div>
  </div>
</div>
</template>

<script>
import axios from 'axios'
import moment from 'moment'
import 'moment/locale/ja'
import AppConfig from '../mixins/AppConfig.js'

export default {
  name: 'app-log',
  mixins: [ AppConfig ],
  data () {
    return {
      pageSize: 10,
      page: 1,
      log: []
    }
  },
  created () {
    this.updateLog()
    this.$eventHub.$on('manual-control', this.updateLogWithDelay)
    this.$eventHub.$on('schedule-setting', this.updateLogWithDelay)
  },
  beforeDestroy () {
    this.$eventHub.$off('manual-control')
    this.$eventHub.$off('schedule-setting')
  },
  methods: {
    updateLog: function () {
      axios
        .get(this.AppConfig['apiEndpoint'] + 'log')
        .then(response => {
          this.log = response.data.data
          for (let entry in this.log) {
            let date = moment(this.log[entry]['date'])
            this.log[entry]['date'] = date.format('M月D日(ddd) HH:mm')
            this.log[entry]['fromNow'] = date.fromNow()
          }
        })
    },
    updateLogWithDelay: function () {
      setTimeout(this.updateLog, 500)
    }
  }
}
</script>

<style>
.page-link {
    color: #28a745 !important;
}
.page-item.active .page-link {
    background-color: #28a745 !important;
    border-color: #28a745 !important;
    color: #ffffff !important;
}
</style>
