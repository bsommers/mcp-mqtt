(function(){
"use strict";
function copy(text,btn){var old=btn.textContent;var done=function(){btn.textContent="Copied";setTimeout(function(){btn.textContent=old},1500)};
if(navigator.clipboard&&navigator.clipboard.writeText){navigator.clipboard.writeText(text).then(done,function(){btn.textContent="Press Ctrl+C"})}else{btn.textContent="Press Ctrl+C"}}
document.querySelectorAll("[data-copy]").forEach(function(b){b.addEventListener("click",function(){copy(document.getElementById(b.dataset.copy).textContent,b)})});
// broker tabs
var tabs=document.querySelectorAll("[role=tab]");
function pick(t){tabs.forEach(function(x){var on=x===t;x.setAttribute("aria-selected",on);x.tabIndex=on?0:-1;document.getElementById(x.getAttribute("aria-controls")).hidden=!on});t.focus()}
tabs.forEach(function(t,i){t.addEventListener("click",function(){pick(t)});t.addEventListener("keydown",function(e){var n=e.key==="ArrowRight"?1:e.key==="ArrowLeft"?-1:0;if(n){e.preventDefault();pick(tabs[(i+n+tabs.length)%tabs.length])}})});
// zoom
var dlg=document.getElementById("zoom");
document.querySelectorAll(".gallery button").forEach(function(b){b.addEventListener("click",function(){var im=b.querySelector("img");var z=dlg.querySelector("img");z.src=im.src;z.alt=im.alt;dlg.querySelector("p").textContent=b.querySelector("span").textContent;if(dlg.showModal){dlg.showModal()}else{dlg.setAttribute("open","")}})});
dlg.querySelector("button").addEventListener("click",function(){dlg.close?dlg.close():dlg.removeAttribute("open")});
dlg.addEventListener("click",function(e){if(e.target===dlg&&dlg.close){dlg.close()}});
// explorer
var q=document.getElementById("q"),cards=document.querySelectorAll(".tool-card"),pills=document.querySelectorAll(".pills button"),cat="all";
function filt(){var s=q.value.toLowerCase();var n=0;cards.forEach(function(c){var ok=(cat==="all"||c.dataset.broker.split(" ").indexOf(cat)>-1)&&c.textContent.toLowerCase().indexOf(s)>-1;c.hidden=!ok;if(ok)n++});document.getElementById("tool-count").textContent=n+" tools shown"}
q.addEventListener("input",filt);
pills.forEach(function(p){p.addEventListener("click",function(){cat=p.dataset.cat;pills.forEach(function(x){x.setAttribute("aria-pressed",x===p)});filt()})});
})();
