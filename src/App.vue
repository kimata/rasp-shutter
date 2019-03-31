<template>
<div id="app">
  <app-header></app-header>
  <div class="container">
    <manual-control></manual-control>
    <schedule-setting></schedule-setting>
  </div>
</div>
</template>

<script>

import AppHeader from './components/AppHeader'
import ManualControl from './components/ManualControl'
import ScheduleSetting from './components/ScheduleSetting'

import Vue from 'vue'
import VueToastr2 from 'vue-toastr-2'
import 'vue-toastr-2/dist/vue-toastr-2.min.css'

window.toastr = require('toastr')

Vue.use(VueToastr2)
// Vue.component('vue-toastr', Toastr)

export default {
  name: 'app',
  components: {
    AppHeader,
    ManualControl,
    ScheduleSetting
  }
}
</script>

<style>
h2 {
    border-bottom: solid 3px #cde6b8;
    position: relative;
}

h2:after {
    position: absolute;
    content: " ";
    display: block;
    border-bottom: solid 3px #82b956;
    bottom: -3px;
    width: 20%;
}
p
h3 {
    font-size: 1.1rem !important;
    margin-top: 1em !important;
}

.toast-success {
    background-color: #51A351 !important;
}

.toast-info {
    background-color: #2f96b4 !important;
}

.toast-error {
    background-color: #bd362f !important;
}
</style>
