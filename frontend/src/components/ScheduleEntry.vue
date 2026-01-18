<template>
    <div class="container">
        <h3>{{ label }}</h3>
        <div class="row">
            <div class="switchToggle mt-1 col-sm-6">
                <input
                    type="checkbox"
                    v-bind:id="name + '-schedule-entry'"
                    name="enabled"
                    v-model="entry.is_active"
                    @change="emit()"
                />
                <label v-bind:for="name + '-schedule-entry'" />
            </div>
        </div>

        <div class="row">
            <h3>時刻</h3>
            <div class="form-group">
                <div class="input-group" v-bind:id="name + '-schedule-entry-time'">
                    <input
                        type="time"
                        class="form-control"
                        name="time"
                        v-model="entry.time"
                        v-bind:disabled="!entry.is_active"
                        @input="emit()"
                    />
                    <div class="input-group-append">
                        <div class="input-group-text time-icon"></div>
                    </div>
                </div>
            </div>
        </div>
        <div class="row mt-3">
            <small v-if="name == 'open'" class="text-success">午前、高度・日射・照度が共に上回ったら開きます。</small>
            <small v-else class="text-success">高度・日射・照度のいずれかが下回ったら閉じます。</small>
        </div>
        <div class="row">
            <h3>日射閾値</h3>
            <div class="form-group">
                <div class="input-group" v-bind:id="name + '-schedule-entry-solar_rad'">
                    <input
                        type="number"
                        class="form-control text-end"
                        name="sorlar_rad"
                        v-model="entry.solar_rad"
                        v-bind:disabled="!entry.is_active"
                        @input="emit()"
                    />
                    <div class="input-group-append">
                        <div class="input-group-text" style="width: 4em">W/m<sup>2</sup></div>
                    </div>
                </div>
            </div>
        </div>

        <div class="row">
            <h3>照度閾値</h3>
            <div class="form-group">
                <div class="input-group" v-bind:id="name + '-schedule-entry-lux'">
                    <input
                        type="number"
                        class="form-control text-end"
                        name="lux"
                        v-model="entry.lux"
                        v-bind:disabled="!entry.is_active"
                        @input="emit()"
                    />
                    <div class="input-group-append">
                        <div class="input-group-text" style="width: 4em">LUX</div>
                    </div>
                </div>
            </div>
        </div>

        <div class="row">
            <h3>太陽高度閾値</h3>
            <div class="form-group">
                <div class="input-group" v-bind:id="name + '-schedule-entry-altitude'">
                    <input
                        type="number"
                        class="form-control text-end"
                        name="altitude"
                        v-model="entry.altitude"
                        v-bind:disabled="!entry.is_active"
                        @input="emit()"
                    />
                    <div class="input-group-append">
                        <div class="input-group-text" style="width: 4em">度</div>
                    </div>
                </div>
            </div>
        </div>

        <div class="row">
            <h3>曜日</h3>
            <div v-bind:id="name + '-schedule-entry-wday'">
                <span
                    v-for="(wday, i) in ['日', '月', '火', '水', '木', '金', '土']"
                    :key="name + '-wday-' + i"
                    class="me-2"
                >
                    <input
                        type="checkbox"
                        name="wday"
                        v-bind:id="name + '-wday-' + i"
                        v-model="entry.wday[i]"
                        @click="changeWday($event, i)"
                        @change="emit()"
                    />
                    <label v-bind:for="name + '-wday-' + i">{{ wday }}</label>
                </span>
            </div>
        </div>
    </div>
</template>

<script>
export default {
    name: "schedule-entry",
    compatConfig: { MODE: 3 },
    props: ["modelValue", "label", "name"],
    computed: {
        entry() {
            return {
                is_active: this.modelValue.is_active,
                time: this.modelValue.time,
                solar_rad: this.modelValue.solar_rad,
                lux: this.modelValue.lux,
                altitude: this.modelValue.altitude,
                wday: this.modelValue.wday,
            };
        },
    },
    emits: ["update:modelValue"],

    methods: {
        emit: function () {
            this.$emit("update:modelValue", this.entry);
        },
        changeWday: function (event, i) {
            const wday = [...this.entry.wday];
            wday[i] = !wday[i];
            if (wday.filter((x) => x).length == 0) {
                this.$root.$toast.open({
                    type: "error",
                    position: "top-right",
                    message: "いずれかの曜日を選択する必要があります。",
                });
                event.preventDefault();
            }
        },
    },
};
</script>

<style scoped>
.input-group > .input-group-append > .input-group-text {
    border-top-left-radius: 0;
    border-bottom-left-radius: 0;
}

.switchToggle input[type="checkbox"] {
    height: 0;
    width: 0;
    visibility: hidden;
    position: absolute;
}
.switchToggle label {
    cursor: pointer;
    text-indent: -9999px;
    width: 80px;
    max-width: 80px;
    height: 30px;
    background: #d1d1d1;
    display: block;
    border-radius: 100px;
    position: relative;
}
.switchToggle label:after {
    content: "";
    position: absolute;
    top: 2px;
    left: 2px;
    width: 26px;
    height: 26px;
    background: #fff;
    border-radius: 90px;
    transition: 0.3s;
}
.switchToggle input:checked + label,
.switchToggle input:checked + input + label {
    background: #28a745;
}
.switchToggle input + label:before,
.switchToggle input + input + label:before {
    content: "OFF";
    position: absolute;
    top: 3px;
    left: 35px;
    width: 26px;
    height: 26px;
    border-radius: 90px;
    transition: 0.3s;
    text-indent: 0;
    color: #fff;
}
.switchToggle input:checked + label:before,
.switchToggle input:checked + input + label:before {
    content: "ON";
    position: absolute;
    top: 3px;
    left: 10px;
    width: 26px;
    height: 26px;
    border-radius: 90px;
    transition: 0.3s;
    text-indent: 0;
    color: #fff;
}
.switchToggle input:checked + label:after,
.switchToggle input:checked + input + label:after {
    left: calc(100% - 2px);
    transform: translateX(-100%);
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

.sun-icon:after {
    content: "\1f31e";
}

.lux-icon:after {
    content: "\1f4a1";
}

.fa-arrow-down:before {
    content: "\25BC";
}

.fa-arrow-up:before {
    content: "\25B2";
}

.switchToggle input + label:before,
.switchToggle input + input + label:before {
    content: "無効";
    width: 40px;
}
.switchToggle input:checked + label:before,
.switchToggle input:checked + input + label:before {
    content: "有効";
    width: 40px;
}
</style>
