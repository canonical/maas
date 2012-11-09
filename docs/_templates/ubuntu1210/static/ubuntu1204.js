(function () {
  $(document).ready(function () {
    $('.nav-secondary').each(function() {
    $(this).find('ul').each(function(index, item) {
    $(this).find('li').each(function() {
    $('.nav-secondary ul').first().addClass('clearfix').append(this);}); }); });
    $('.nav-secondary ul ul').remove();
    $('.nav-secondary a.internal').first().remove();
    prettyPrint();
  });
}());

(function() {
  var wf = document.createElement('script');
  wf.src = ('https:' == document.location.protocol ? 'https' : 'http') +
    '://ajax.googleapis.com/ajax/libs/webfont/1/webfont.js';
  wf.type = 'text/javascript';
  wf.async = 'true';
  var s = document.getElementsByTagName('script')[0];
  s.parentNode.insertBefore(wf, s); 
})();

var _gaq = _gaq || [];_gaq.push(['_setAccount', 'UA-1997599-7']);_gaq.push(['_trackPageview']);
(function() {
  var ga = document.createElement('script'); ga.type = 'text/javascript'; ga.async = true;
  ga.src = 'https://ssl.google-analytics.com/ga.js';var s = document.getElementsByTagName('script')[0]; s.parentNode.insertBefore(ga, s);
})();
    