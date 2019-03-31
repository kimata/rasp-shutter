<template>
<div class="row mb-4 mt-4">
  <div class="col-xl-6 offset-xl-3 col-lg-8 offset-lg-2 col-md-10 offset-md-1">
    <h2>自動</h2>
    <form class="schedule-setting">
      <div class="container">
        <h3>オープン</h3>
        <div class="row">
          <div class="switchToggle mt-1 col-lg-6 col-md-4">
            <input type="checkbox" id="schedule-entry-open" name="enabled"
                   v-model="current.open.is_active" />
            <label for="schedule-entry-open"></label>
          </div>
          <div class="form-group col-lg-6 col-md-8">
            <div class="input-group" id="schedule-entry-time">
              <input type="time" class="form-control" name="time"
                     v-model="current.open.time"
                     v-bind:disabled="!current.open.is_active" />
              <div class="input-group-append">
                <div class="input-group-text time-icon"></div>
              </div>
            </div>
          </div>
        </div>
      </div>
      <div class="container">
        <h3>クローズ</h3>
        <div class="row">
          <div class="switchToggle mt-1 col-lg-6 col-md-4">
            <input type="checkbox" id="schedule-entry-close" name="enabled"
                   v-model="current.close.is_active" />
            <label for="schedule-entry-close"></label>
          </div>
          <div class="form-group col-lg-6 col-md-8">
            <div class="input-group" id="schedule-entry-time">
              <input type="time" class="form-control" name="time"
                     v-model="current.close.time"
                     v-bind:disabled="!current.close.is_active" />
              <div class="input-group-append">
                <div class="input-group-text time-icon"></div>
              </div>
            </div>
          </div>
        </div>
      </div>
      <div class="container mt-2">
        <button type="button" class="btn btn-success col"
                @click="save()" v-bind:disabled="!isChanged()">保存</button>
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
      current: {
        open: { },
        close: { }
      },
      saved: { }
    }
  },
  created () {
    axios
      .get(this.AppConfig['apiEndpoint'] + 'schedule_ctrl')
      .then(response => {
        this.current = response.data
        this.saved = JSON.parse(JSON.stringify(response.data)) // NOTE: deep copy
      })
  },
  methods: {
    save: function () {
      axios
        .get(this.AppConfig['apiEndpoint'] + 'schedule_ctrl', {
          params: { set: JSON.stringify(this.current) }
        })
        .then(response => {
          this.saved = response.data
          this.$root.$toastr.success('正常に保存できました．', '成功')
        })
        .catch(_ => {
          this.$root.$toastr.error('保存に失敗しました．', 'エラー')
        })
    },
    isChanged: function () {
      return this.isStateDiffer(this.current, this.saved)
    },
    isStateDiffer: function (a, b) {
      let isDiffer = false
      for (let mode in a) {
        for (let key in a[mode]) {
          if (a[mode][key] !== b[mode][key]) {
            isDiffer = true
          }
        }
      }
      return isDiffer
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
