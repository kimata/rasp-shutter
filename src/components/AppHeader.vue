<template>
<header>
  <div class="col-xl-6 offset-xl-3 col-lg-8 offset-lg-2 col-md-10 offset-md-1">
    <div class="jumbotron">
      <h1>シャッター制御</h1>
    </div>
  </div>
</header>
</template>

<script>
export default {
  name: 'app-header',
  data () {
    return {
      msg: 'Welcome to Your Vue.js App'
    }
  }
}
</script>

<style scoped>
.jumbotron {
    height: 5em;
    background-image: url('../assets/img/logo.png');
    background-repeat: no-repeat;
    background-size: auto 4em;
    background-position: 95%;
}
.jumbotron h1 {
    font-size: 2.2rem;
    margin-top: -0.8em;
}
</style>
