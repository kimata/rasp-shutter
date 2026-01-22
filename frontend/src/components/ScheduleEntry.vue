<template>
    <div>
        <h3>{{ label }}</h3>
        <div class="flex">
            <div class="switchToggle mt-1">
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

        <div>
            <h3>時刻</h3>
            <div class="input-group" v-bind:id="name + '-schedule-entry-time'">
                <input
                    type="time"
                    class="form-input flex-1 rounded-l border border-gray-300 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-green-500"
                    name="time"
                    v-model="entry.time"
                    v-bind:disabled="!entry.is_active"
                    @input="emit()"
                />
                <div
                    class="input-group-text time-icon rounded-r border border-l-0 border-gray-300 bg-gray-100 px-3 py-2 w-16"
                ></div>
            </div>
        </div>
        <div class="mt-3">
            <small v-if="name == 'open'" class="text-green-600"
                >午前、高度・日射・照度が共に上回ったら開きます。</small
            >
            <small v-else class="text-green-600">高度・日射・照度のいずれかが下回ったら閉じます。</small>
        </div>
        <div>
            <h3>日射閾値</h3>
            <div class="input-group" v-bind:id="name + '-schedule-entry-solar_rad'">
                <input
                    type="number"
                    class="form-input flex-1 rounded-l border border-gray-300 px-3 py-2 text-right focus:outline-none focus:ring-2 focus:ring-green-500"
                    name="sorlar_rad"
                    v-model="entry.solar_rad"
                    v-bind:disabled="!entry.is_active"
                    @input="emit()"
                />
                <div
                    class="input-group-text rounded-r border border-l-0 border-gray-300 bg-gray-100 px-3 py-2 w-16"
                >
                    W/m<sup>2</sup>
                </div>
            </div>
        </div>

        <div>
            <h3>照度閾値</h3>
            <div class="input-group" v-bind:id="name + '-schedule-entry-lux'">
                <input
                    type="number"
                    class="form-input flex-1 rounded-l border border-gray-300 px-3 py-2 text-right focus:outline-none focus:ring-2 focus:ring-green-500"
                    name="lux"
                    v-model="entry.lux"
                    v-bind:disabled="!entry.is_active"
                    @input="emit()"
                />
                <div
                    class="input-group-text rounded-r border border-l-0 border-gray-300 bg-gray-100 px-3 py-2 w-16"
                >
                    LUX
                </div>
            </div>
        </div>

        <div>
            <h3>太陽高度閾値</h3>
            <div class="input-group" v-bind:id="name + '-schedule-entry-altitude'">
                <input
                    type="number"
                    class="form-input flex-1 rounded-l border border-gray-300 px-3 py-2 text-right focus:outline-none focus:ring-2 focus:ring-green-500"
                    name="altitude"
                    v-model="entry.altitude"
                    v-bind:disabled="!entry.is_active"
                    @input="emit()"
                />
                <div
                    class="input-group-text rounded-r border border-l-0 border-gray-300 bg-gray-100 px-3 py-2 w-16"
                >
                    度
                </div>
            </div>
        </div>

        <div>
            <h3>曜日</h3>
            <div v-bind:id="name + '-schedule-entry-wday'" class="flex flex-wrap gap-1">
                <label
                    v-for="(wday, i) in ['日', '月', '火', '水', '木', '金', '土']"
                    :key="name + '-wday-' + i"
                    :for="name + '-wday-' + i"
                    class="wday-toggle"
                    :class="[
                        entry.wday[i]
                            ? 'bg-green-600 text-white border-green-600'
                            : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50',
                        i === 0 ? 'text-red-500' : '',
                        i === 6 ? 'text-blue-500' : '',
                        entry.wday[i] && (i === 0 || i === 6) ? '!text-white' : '',
                    ]"
                >
                    <input
                        type="checkbox"
                        name="wday"
                        :id="name + '-wday-' + i"
                        v-model="entry.wday[i]"
                        @click="changeWday($event, i)"
                        @change="emit()"
                        class="sr-only"
                    />
                    {{ wday }}
                </label>
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
.input-group {
    display: flex;
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
    background: #16a34a;
}
.switchToggle input + label:before,
.switchToggle input + input + label:before {
    content: "無効";
    position: absolute;
    top: 3px;
    left: 35px;
    width: 40px;
    height: 26px;
    border-radius: 90px;
    transition: 0.3s;
    text-indent: 0;
    color: #fff;
}
.switchToggle input:checked + label:before,
.switchToggle input:checked + input + label:before {
    content: "有効";
    position: absolute;
    top: 3px;
    left: 10px;
    width: 40px;
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

.wday-toggle {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 2.5rem;
    height: 2.5rem;
    border-width: 1px;
    border-radius: 9999px;
    cursor: pointer;
    font-weight: 500;
    transition: all 0.2s;
    user-select: none;
}

.sr-only {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    white-space: nowrap;
    border-width: 0;
}
</style>
