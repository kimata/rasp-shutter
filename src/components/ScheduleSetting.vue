<template>
<div class="row mb-4">
  <div class="col-xl-6 offset-xl-3 col-lg-8 offset-lg-2 col-md-10 offset-md-1">
    <h2>スケジュール</h2>
    <form class="schedule-setting">
      <div class="container">
        <div class="switchToggle mt-3">
          <input type="checkbox" id="schedule-entry" name="enabled"
                 />
          <label for="schedule-entry"></label>
        </div>
      </div>
      <div class="container">
        <h3>上げる時刻</h3>
        <div class="form-group">
          <div class="input-group" id="schedule-entry-time">
            <input type="time" class="form-control"
                   name="time"
                   />
            <div class="input-group-append">
              <div class="input-group-text time-icon"></div>
            </div>
          </div>
        </div>
      </div>
      <div class="container">
        <h3>下げる時刻</h3>
        <div class="form-group">
          <div class="input-group" id="schedule-entry-time">
            <input type="time" class="form-control"
                   name="time"
                   />
            <div class="input-group-append">
              <div class="input-group-text time-icon"></div>
            </div>
          </div>
        </div>
      </div>
      <div class="container">
      <button type="button" class="btn btn-success col">保存</button>
      </div>
    </form>
  </div>
</div>
</template>

<script>
import axios from 'axios'
import AppConfig from '../mixins/AppConfig.js'

export default {
  name: 'schedule-setting',
  mixins: [ AppConfig ],
  data () {
    return {
      isActive: false,
      timeOpen: 0,
      timeClose: 0
    }
  },
  methods: {
    control: function () {
      axios
        .get('https://api.coindesk.com/v1/bpi/currentprice.json')
        .then(response => (console.log(response)))
    }
  }
}
</script>

<!-- Add "scoped" attribute to limit CSS to this component only -->
<style scoped>
.switchToggle input[type=checkbox] {
    height: 0; width: 0; visibility: hidden; position: absolute;
}
.switchToggle label {
    cursor: pointer; text-indent: -9999px; width: 80px; max-width: 80px;
    height: 30px; background: #d1d1d1; display: block; border-radius: 100px; position: relative;
}
.switchToggle label:after {
    content: ''; position: absolute; top: 2px; left: 2px; width: 26px; height: 26px;
    background: #fff; border-radius: 90px; transition: 0.3s;
}
.switchToggle input:checked + label, .switchToggle input:checked + input + label {
    background: #28a745;
}
.switchToggle input + label:before, .switchToggle input + input + label:before {
    content: 'OFF'; position: absolute; top: 5px; left: 35px; width: 26px; height: 26px;
    border-radius: 90px; transition: 0.3s; text-indent: 0; color: #fff;
}
.switchToggle input:checked + label:before, .switchToggle input:checked + input + label:before {
    content: 'ON'; position: absolute; top: 5px; left: 10px; width: 26px; height: 26px;
    border-radius: 90px; transition: 0.3s; text-indent: 0; color: #fff;
}
.switchToggle input:checked + label:after, .switchToggle input:checked + input + label:after {
    left: calc(100% - 2px); transform: translateX(-100%);
}
.switchToggle label:active:after {
    width: 60px;
}

.input-group-text {
    font-family: "Segoe UI Emoji";
}

.time-icon:before {
    content: "\1f55b";
}

.fa-arrow-down:before {
    content: "\25BC";
}

.fa-arrow-up:before {
    content: "\25B2";
}

.switchToggle input + label:before, .switchToggle input + input + label:before {
    content: '無効';
    width: 40px;
}
.switchToggle input:checked + label:before, .switchToggle input:checked + input + label:before {
    content: '有効';
    width: 40px;
}
</style>
