// ==UserScript==
// @name         烤推
// @namespace    https://github.com/chenxuan353/tampermonkey/
// @version      0.1
// @description  通过JS脚本烤推注入的烤推机，未来可能集成至扩展中。拥有友好界面，由于推特严格的CSP限制，故使用了GM_addElement，需要油猴4.11+。支持无需UI的控制台模式，在控制台中使用全局定义的trans(待解析文本，模版)即可。
// @author       chenxuan
// @match        https://twitter.com/*
// @grant        unsafeWindow
// @run-at       document-start
// @grant        GM_getResourceText
// @grant        GM_addStyle
// @grant        GM_setValue
// @grant        GM_getValue
// @grant        GM_addElement
// @grant        GM_log
// @require      https://cdn.bootcdn.net/ajax/libs/jquery/3.6.0/jquery.js
// ==/UserScript==
// 推特emoji
/*! Copyright Twitter Inc. and other contributors. Licensed under MIT */
var twemoji = (function () {
    "use strict";
    var twemoji = {
            base: "https://twemoji.maxcdn.com/v/14.0.2/",
            ext: ".png",
            size: "72x72",
            className: "emoji",
            convert: { fromCodePoint: fromCodePoint, toCodePoint: toCodePoint },
            onerror: function onerror() {
                if (this.parentNode) {
                    this.parentNode.replaceChild(
                        createText(this.alt, false),
                        this,
                    );
                }
            },
            parse: parse,
            replace: replace,
            test: test,
        },
        escaper = {
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            "'": "&#39;",
            '"': "&quot;",
        },
        re =
            /(?:\ud83d\udc68\ud83c\udffb\u200d\u2764\ufe0f\u200d\ud83d\udc8b\u200d\ud83d\udc68\ud83c[\udffb-\udfff]|\ud83d\udc68\ud83c\udffc\u200d\u2764\ufe0f\u200d\ud83d\udc8b\u200d\ud83d\udc68\ud83c[\udffb-\udfff]|\ud83d\udc68\ud83c\udffd\u200d\u2764\ufe0f\u200d\ud83d\udc8b\u200d\ud83d\udc68\ud83c[\udffb-\udfff]|\ud83d\udc68\ud83c\udffe\u200d\u2764\ufe0f\u200d\ud83d\udc8b\u200d\ud83d\udc68\ud83c[\udffb-\udfff]|\ud83d\udc68\ud83c\udfff\u200d\u2764\ufe0f\u200d\ud83d\udc8b\u200d\ud83d\udc68\ud83c[\udffb-\udfff]|\ud83d\udc69\ud83c\udffb\u200d\u2764\ufe0f\u200d\ud83d\udc8b\u200d\ud83d\udc68\ud83c[\udffb-\udfff]|\ud83d\udc69\ud83c\udffb\u200d\u2764\ufe0f\u200d\ud83d\udc8b\u200d\ud83d\udc69\ud83c[\udffb-\udfff]|\ud83d\udc69\ud83c\udffc\u200d\u2764\ufe0f\u200d\ud83d\udc8b\u200d\ud83d\udc68\ud83c[\udffb-\udfff]|\ud83d\udc69\ud83c\udffc\u200d\u2764\ufe0f\u200d\ud83d\udc8b\u200d\ud83d\udc69\ud83c[\udffb-\udfff]|\ud83d\udc69\ud83c\udffd\u200d\u2764\ufe0f\u200d\ud83d\udc8b\u200d\ud83d\udc68\ud83c[\udffb-\udfff]|\ud83d\udc69\ud83c\udffd\u200d\u2764\ufe0f\u200d\ud83d\udc8b\u200d\ud83d\udc69\ud83c[\udffb-\udfff]|\ud83d\udc69\ud83c\udffe\u200d\u2764\ufe0f\u200d\ud83d\udc8b\u200d\ud83d\udc68\ud83c[\udffb-\udfff]|\ud83d\udc69\ud83c\udffe\u200d\u2764\ufe0f\u200d\ud83d\udc8b\u200d\ud83d\udc69\ud83c[\udffb-\udfff]|\ud83d\udc69\ud83c\udfff\u200d\u2764\ufe0f\u200d\ud83d\udc8b\u200d\ud83d\udc68\ud83c[\udffb-\udfff]|\ud83d\udc69\ud83c\udfff\u200d\u2764\ufe0f\u200d\ud83d\udc8b\u200d\ud83d\udc69\ud83c[\udffb-\udfff]|\ud83e\uddd1\ud83c\udffb\u200d\u2764\ufe0f\u200d\ud83d\udc8b\u200d\ud83e\uddd1\ud83c[\udffc-\udfff]|\ud83e\uddd1\ud83c\udffc\u200d\u2764\ufe0f\u200d\ud83d\udc8b\u200d\ud83e\uddd1\ud83c[\udffb\udffd-\udfff]|\ud83e\uddd1\ud83c\udffd\u200d\u2764\ufe0f\u200d\ud83d\udc8b\u200d\ud83e\uddd1\ud83c[\udffb\udffc\udffe\udfff]|\ud83e\uddd1\ud83c\udffe\u200d\u2764\ufe0f\u200d\ud83d\udc8b\u200d\ud83e\uddd1\ud83c[\udffb-\udffd\udfff]|\ud83e\uddd1\ud83c\udfff\u200d\u2764\ufe0f\u200d\ud83d\udc8b\u200d\ud83e\uddd1\ud83c[\udffb-\udffe]|\ud83d\udc68\ud83c\udffb\u200d\u2764\ufe0f\u200d\ud83d\udc68\ud83c[\udffb-\udfff]|\ud83d\udc68\ud83c\udffb\u200d\ud83e\udd1d\u200d\ud83d\udc68\ud83c[\udffc-\udfff]|\ud83d\udc68\ud83c\udffc\u200d\u2764\ufe0f\u200d\ud83d\udc68\ud83c[\udffb-\udfff]|\ud83d\udc68\ud83c\udffc\u200d\ud83e\udd1d\u200d\ud83d\udc68\ud83c[\udffb\udffd-\udfff]|\ud83d\udc68\ud83c\udffd\u200d\u2764\ufe0f\u200d\ud83d\udc68\ud83c[\udffb-\udfff]|\ud83d\udc68\ud83c\udffd\u200d\ud83e\udd1d\u200d\ud83d\udc68\ud83c[\udffb\udffc\udffe\udfff]|\ud83d\udc68\ud83c\udffe\u200d\u2764\ufe0f\u200d\ud83d\udc68\ud83c[\udffb-\udfff]|\ud83d\udc68\ud83c\udffe\u200d\ud83e\udd1d\u200d\ud83d\udc68\ud83c[\udffb-\udffd\udfff]|\ud83d\udc68\ud83c\udfff\u200d\u2764\ufe0f\u200d\ud83d\udc68\ud83c[\udffb-\udfff]|\ud83d\udc68\ud83c\udfff\u200d\ud83e\udd1d\u200d\ud83d\udc68\ud83c[\udffb-\udffe]|\ud83d\udc69\ud83c\udffb\u200d\u2764\ufe0f\u200d\ud83d\udc68\ud83c[\udffb-\udfff]|\ud83d\udc69\ud83c\udffb\u200d\u2764\ufe0f\u200d\ud83d\udc69\ud83c[\udffb-\udfff]|\ud83d\udc69\ud83c\udffb\u200d\ud83e\udd1d\u200d\ud83d\udc68\ud83c[\udffc-\udfff]|\ud83d\udc69\ud83c\udffb\u200d\ud83e\udd1d\u200d\ud83d\udc69\ud83c[\udffc-\udfff]|\ud83d\udc69\ud83c\udffc\u200d\u2764\ufe0f\u200d\ud83d\udc68\ud83c[\udffb-\udfff]|\ud83d\udc69\ud83c\udffc\u200d\u2764\ufe0f\u200d\ud83d\udc69\ud83c[\udffb-\udfff]|\ud83d\udc69\ud83c\udffc\u200d\ud83e\udd1d\u200d\ud83d\udc68\ud83c[\udffb\udffd-\udfff]|\ud83d\udc69\ud83c\udffc\u200d\ud83e\udd1d\u200d\ud83d\udc69\ud83c[\udffb\udffd-\udfff]|\ud83d\udc69\ud83c\udffd\u200d\u2764\ufe0f\u200d\ud83d\udc68\ud83c[\udffb-\udfff]|\ud83d\udc69\ud83c\udffd\u200d\u2764\ufe0f\u200d\ud83d\udc69\ud83c[\udffb-\udfff]|\ud83d\udc69\ud83c\udffd\u200d\ud83e\udd1d\u200d\ud83d\udc68\ud83c[\udffb\udffc\udffe\udfff]|\ud83d\udc69\ud83c\udffd\u200d\ud83e\udd1d\u200d\ud83d\udc69\ud83c[\udffb\udffc\udffe\udfff]|\ud83d\udc69\ud83c\udffe\u200d\u2764\ufe0f\u200d\ud83d\udc68\ud83c[\udffb-\udfff]|\ud83d\udc69\ud83c\udffe\u200d\u2764\ufe0f\u200d\ud83d\udc69\ud83c[\udffb-\udfff]|\ud83d\udc69\ud83c\udffe\u200d\ud83e\udd1d\u200d\ud83d\udc68\ud83c[\udffb-\udffd\udfff]|\ud83d\udc69\ud83c\udffe\u200d\ud83e\udd1d\u200d\ud83d\udc69\ud83c[\udffb-\udffd\udfff]|\ud83d\udc69\ud83c\udfff\u200d\u2764\ufe0f\u200d\ud83d\udc68\ud83c[\udffb-\udfff]|\ud83d\udc69\ud83c\udfff\u200d\u2764\ufe0f\u200d\ud83d\udc69\ud83c[\udffb-\udfff]|\ud83d\udc69\ud83c\udfff\u200d\ud83e\udd1d\u200d\ud83d\udc68\ud83c[\udffb-\udffe]|\ud83d\udc69\ud83c\udfff\u200d\ud83e\udd1d\u200d\ud83d\udc69\ud83c[\udffb-\udffe]|\ud83e\uddd1\ud83c\udffb\u200d\u2764\ufe0f\u200d\ud83e\uddd1\ud83c[\udffc-\udfff]|\ud83e\uddd1\ud83c\udffb\u200d\ud83e\udd1d\u200d\ud83e\uddd1\ud83c[\udffb-\udfff]|\ud83e\uddd1\ud83c\udffc\u200d\u2764\ufe0f\u200d\ud83e\uddd1\ud83c[\udffb\udffd-\udfff]|\ud83e\uddd1\ud83c\udffc\u200d\ud83e\udd1d\u200d\ud83e\uddd1\ud83c[\udffb-\udfff]|\ud83e\uddd1\ud83c\udffd\u200d\u2764\ufe0f\u200d\ud83e\uddd1\ud83c[\udffb\udffc\udffe\udfff]|\ud83e\uddd1\ud83c\udffd\u200d\ud83e\udd1d\u200d\ud83e\uddd1\ud83c[\udffb-\udfff]|\ud83e\uddd1\ud83c\udffe\u200d\u2764\ufe0f\u200d\ud83e\uddd1\ud83c[\udffb-\udffd\udfff]|\ud83e\uddd1\ud83c\udffe\u200d\ud83e\udd1d\u200d\ud83e\uddd1\ud83c[\udffb-\udfff]|\ud83e\uddd1\ud83c\udfff\u200d\u2764\ufe0f\u200d\ud83e\uddd1\ud83c[\udffb-\udffe]|\ud83e\uddd1\ud83c\udfff\u200d\ud83e\udd1d\u200d\ud83e\uddd1\ud83c[\udffb-\udfff]|\ud83d\udc68\u200d\u2764\ufe0f\u200d\ud83d\udc8b\u200d\ud83d\udc68|\ud83d\udc69\u200d\u2764\ufe0f\u200d\ud83d\udc8b\u200d\ud83d[\udc68\udc69]|\ud83e\udef1\ud83c\udffb\u200d\ud83e\udef2\ud83c[\udffc-\udfff]|\ud83e\udef1\ud83c\udffc\u200d\ud83e\udef2\ud83c[\udffb\udffd-\udfff]|\ud83e\udef1\ud83c\udffd\u200d\ud83e\udef2\ud83c[\udffb\udffc\udffe\udfff]|\ud83e\udef1\ud83c\udffe\u200d\ud83e\udef2\ud83c[\udffb-\udffd\udfff]|\ud83e\udef1\ud83c\udfff\u200d\ud83e\udef2\ud83c[\udffb-\udffe]|\ud83d\udc68\u200d\u2764\ufe0f\u200d\ud83d\udc68|\ud83d\udc69\u200d\u2764\ufe0f\u200d\ud83d[\udc68\udc69]|\ud83e\uddd1\u200d\ud83e\udd1d\u200d\ud83e\uddd1|\ud83d\udc6b\ud83c[\udffb-\udfff]|\ud83d\udc6c\ud83c[\udffb-\udfff]|\ud83d\udc6d\ud83c[\udffb-\udfff]|\ud83d\udc8f\ud83c[\udffb-\udfff]|\ud83d\udc91\ud83c[\udffb-\udfff]|\ud83e\udd1d\ud83c[\udffb-\udfff]|\ud83d[\udc6b-\udc6d\udc8f\udc91]|\ud83e\udd1d)|(?:\ud83d[\udc68\udc69]|\ud83e\uddd1)(?:\ud83c[\udffb-\udfff])?\u200d(?:\u2695\ufe0f|\u2696\ufe0f|\u2708\ufe0f|\ud83c[\udf3e\udf73\udf7c\udf84\udf93\udfa4\udfa8\udfeb\udfed]|\ud83d[\udcbb\udcbc\udd27\udd2c\ude80\ude92]|\ud83e[\uddaf-\uddb3\uddbc\uddbd])|(?:\ud83c[\udfcb\udfcc]|\ud83d[\udd74\udd75]|\u26f9)((?:\ud83c[\udffb-\udfff]|\ufe0f)\u200d[\u2640\u2642]\ufe0f)|(?:\ud83c[\udfc3\udfc4\udfca]|\ud83d[\udc6e\udc70\udc71\udc73\udc77\udc81\udc82\udc86\udc87\ude45-\ude47\ude4b\ude4d\ude4e\udea3\udeb4-\udeb6]|\ud83e[\udd26\udd35\udd37-\udd39\udd3d\udd3e\uddb8\uddb9\uddcd-\uddcf\uddd4\uddd6-\udddd])(?:\ud83c[\udffb-\udfff])?\u200d[\u2640\u2642]\ufe0f|(?:\ud83d\udc68\u200d\ud83d\udc68\u200d\ud83d\udc66\u200d\ud83d\udc66|\ud83d\udc68\u200d\ud83d\udc68\u200d\ud83d\udc67\u200d\ud83d[\udc66\udc67]|\ud83d\udc68\u200d\ud83d\udc69\u200d\ud83d\udc66\u200d\ud83d\udc66|\ud83d\udc68\u200d\ud83d\udc69\u200d\ud83d\udc67\u200d\ud83d[\udc66\udc67]|\ud83d\udc69\u200d\ud83d\udc69\u200d\ud83d\udc66\u200d\ud83d\udc66|\ud83d\udc69\u200d\ud83d\udc69\u200d\ud83d\udc67\u200d\ud83d[\udc66\udc67]|\ud83d\udc68\u200d\ud83d\udc66\u200d\ud83d\udc66|\ud83d\udc68\u200d\ud83d\udc67\u200d\ud83d[\udc66\udc67]|\ud83d\udc68\u200d\ud83d\udc68\u200d\ud83d[\udc66\udc67]|\ud83d\udc68\u200d\ud83d\udc69\u200d\ud83d[\udc66\udc67]|\ud83d\udc69\u200d\ud83d\udc66\u200d\ud83d\udc66|\ud83d\udc69\u200d\ud83d\udc67\u200d\ud83d[\udc66\udc67]|\ud83d\udc69\u200d\ud83d\udc69\u200d\ud83d[\udc66\udc67]|\ud83c\udff3\ufe0f\u200d\u26a7\ufe0f|\ud83c\udff3\ufe0f\u200d\ud83c\udf08|\ud83d\ude36\u200d\ud83c\udf2b\ufe0f|\u2764\ufe0f\u200d\ud83d\udd25|\u2764\ufe0f\u200d\ud83e\ude79|\ud83c\udff4\u200d\u2620\ufe0f|\ud83d\udc15\u200d\ud83e\uddba|\ud83d\udc3b\u200d\u2744\ufe0f|\ud83d\udc41\u200d\ud83d\udde8|\ud83d\udc68\u200d\ud83d[\udc66\udc67]|\ud83d\udc69\u200d\ud83d[\udc66\udc67]|\ud83d\udc6f\u200d\u2640\ufe0f|\ud83d\udc6f\u200d\u2642\ufe0f|\ud83d\ude2e\u200d\ud83d\udca8|\ud83d\ude35\u200d\ud83d\udcab|\ud83e\udd3c\u200d\u2640\ufe0f|\ud83e\udd3c\u200d\u2642\ufe0f|\ud83e\uddde\u200d\u2640\ufe0f|\ud83e\uddde\u200d\u2642\ufe0f|\ud83e\udddf\u200d\u2640\ufe0f|\ud83e\udddf\u200d\u2642\ufe0f|\ud83d\udc08\u200d\u2b1b)|[#*0-9]\ufe0f?\u20e3|(?:[©®\u2122\u265f]\ufe0f)|(?:\ud83c[\udc04\udd70\udd71\udd7e\udd7f\ude02\ude1a\ude2f\ude37\udf21\udf24-\udf2c\udf36\udf7d\udf96\udf97\udf99-\udf9b\udf9e\udf9f\udfcd\udfce\udfd4-\udfdf\udff3\udff5\udff7]|\ud83d[\udc3f\udc41\udcfd\udd49\udd4a\udd6f\udd70\udd73\udd76-\udd79\udd87\udd8a-\udd8d\udda5\udda8\uddb1\uddb2\uddbc\uddc2-\uddc4\uddd1-\uddd3\udddc-\uddde\udde1\udde3\udde8\uddef\uddf3\uddfa\udecb\udecd-\udecf\udee0-\udee5\udee9\udef0\udef3]|[\u203c\u2049\u2139\u2194-\u2199\u21a9\u21aa\u231a\u231b\u2328\u23cf\u23ed-\u23ef\u23f1\u23f2\u23f8-\u23fa\u24c2\u25aa\u25ab\u25b6\u25c0\u25fb-\u25fe\u2600-\u2604\u260e\u2611\u2614\u2615\u2618\u2620\u2622\u2623\u2626\u262a\u262e\u262f\u2638-\u263a\u2640\u2642\u2648-\u2653\u2660\u2663\u2665\u2666\u2668\u267b\u267f\u2692-\u2697\u2699\u269b\u269c\u26a0\u26a1\u26a7\u26aa\u26ab\u26b0\u26b1\u26bd\u26be\u26c4\u26c5\u26c8\u26cf\u26d1\u26d3\u26d4\u26e9\u26ea\u26f0-\u26f5\u26f8\u26fa\u26fd\u2702\u2708\u2709\u270f\u2712\u2714\u2716\u271d\u2721\u2733\u2734\u2744\u2747\u2757\u2763\u2764\u27a1\u2934\u2935\u2b05-\u2b07\u2b1b\u2b1c\u2b50\u2b55\u3030\u303d\u3297\u3299])(?:\ufe0f|(?!\ufe0e))|(?:(?:\ud83c[\udfcb\udfcc]|\ud83d[\udd74\udd75\udd90]|[\u261d\u26f7\u26f9\u270c\u270d])(?:\ufe0f|(?!\ufe0e))|(?:\ud83c[\udf85\udfc2-\udfc4\udfc7\udfca]|\ud83d[\udc42\udc43\udc46-\udc50\udc66-\udc69\udc6e\udc70-\udc78\udc7c\udc81-\udc83\udc85-\udc87\udcaa\udd7a\udd95\udd96\ude45-\ude47\ude4b-\ude4f\udea3\udeb4-\udeb6\udec0\udecc]|\ud83e[\udd0c\udd0f\udd18-\udd1c\udd1e\udd1f\udd26\udd30-\udd39\udd3d\udd3e\udd77\uddb5\uddb6\uddb8\uddb9\uddbb\uddcd-\uddcf\uddd1-\udddd\udec3-\udec5\udef0-\udef6]|[\u270a\u270b]))(?:\ud83c[\udffb-\udfff])?|(?:\ud83c\udff4\udb40\udc67\udb40\udc62\udb40\udc65\udb40\udc6e\udb40\udc67\udb40\udc7f|\ud83c\udff4\udb40\udc67\udb40\udc62\udb40\udc73\udb40\udc63\udb40\udc74\udb40\udc7f|\ud83c\udff4\udb40\udc67\udb40\udc62\udb40\udc77\udb40\udc6c\udb40\udc73\udb40\udc7f|\ud83c\udde6\ud83c[\udde8-\uddec\uddee\uddf1\uddf2\uddf4\uddf6-\uddfa\uddfc\uddfd\uddff]|\ud83c\udde7\ud83c[\udde6\udde7\udde9-\uddef\uddf1-\uddf4\uddf6-\uddf9\uddfb\uddfc\uddfe\uddff]|\ud83c\udde8\ud83c[\udde6\udde8\udde9\uddeb-\uddee\uddf0-\uddf5\uddf7\uddfa-\uddff]|\ud83c\udde9\ud83c[\uddea\uddec\uddef\uddf0\uddf2\uddf4\uddff]|\ud83c\uddea\ud83c[\udde6\udde8\uddea\uddec\udded\uddf7-\uddfa]|\ud83c\uddeb\ud83c[\uddee-\uddf0\uddf2\uddf4\uddf7]|\ud83c\uddec\ud83c[\udde6\udde7\udde9-\uddee\uddf1-\uddf3\uddf5-\uddfa\uddfc\uddfe]|\ud83c\udded\ud83c[\uddf0\uddf2\uddf3\uddf7\uddf9\uddfa]|\ud83c\uddee\ud83c[\udde8-\uddea\uddf1-\uddf4\uddf6-\uddf9]|\ud83c\uddef\ud83c[\uddea\uddf2\uddf4\uddf5]|\ud83c\uddf0\ud83c[\uddea\uddec-\uddee\uddf2\uddf3\uddf5\uddf7\uddfc\uddfe\uddff]|\ud83c\uddf1\ud83c[\udde6-\udde8\uddee\uddf0\uddf7-\uddfb\uddfe]|\ud83c\uddf2\ud83c[\udde6\udde8-\udded\uddf0-\uddff]|\ud83c\uddf3\ud83c[\udde6\udde8\uddea-\uddec\uddee\uddf1\uddf4\uddf5\uddf7\uddfa\uddff]|\ud83c\uddf4\ud83c\uddf2|\ud83c\uddf5\ud83c[\udde6\uddea-\udded\uddf0-\uddf3\uddf7-\uddf9\uddfc\uddfe]|\ud83c\uddf6\ud83c\udde6|\ud83c\uddf7\ud83c[\uddea\uddf4\uddf8\uddfa\uddfc]|\ud83c\uddf8\ud83c[\udde6-\uddea\uddec-\uddf4\uddf7-\uddf9\uddfb\uddfd-\uddff]|\ud83c\uddf9\ud83c[\udde6\udde8\udde9\uddeb-\udded\uddef-\uddf4\uddf7\uddf9\uddfb\uddfc\uddff]|\ud83c\uddfa\ud83c[\udde6\uddec\uddf2\uddf3\uddf8\uddfe\uddff]|\ud83c\uddfb\ud83c[\udde6\udde8\uddea\uddec\uddee\uddf3\uddfa]|\ud83c\uddfc\ud83c[\uddeb\uddf8]|\ud83c\uddfd\ud83c\uddf0|\ud83c\uddfe\ud83c[\uddea\uddf9]|\ud83c\uddff\ud83c[\udde6\uddf2\uddfc]|\ud83c[\udccf\udd8e\udd91-\udd9a\udde6-\uddff\ude01\ude32-\ude36\ude38-\ude3a\ude50\ude51\udf00-\udf20\udf2d-\udf35\udf37-\udf7c\udf7e-\udf84\udf86-\udf93\udfa0-\udfc1\udfc5\udfc6\udfc8\udfc9\udfcf-\udfd3\udfe0-\udff0\udff4\udff8-\udfff]|\ud83d[\udc00-\udc3e\udc40\udc44\udc45\udc51-\udc65\udc6a\udc6f\udc79-\udc7b\udc7d-\udc80\udc84\udc88-\udc8e\udc90\udc92-\udca9\udcab-\udcfc\udcff-\udd3d\udd4b-\udd4e\udd50-\udd67\udda4\uddfb-\ude44\ude48-\ude4a\ude80-\udea2\udea4-\udeb3\udeb7-\udebf\udec1-\udec5\uded0-\uded2\uded5-\uded7\udedd-\udedf\udeeb\udeec\udef4-\udefc\udfe0-\udfeb\udff0]|\ud83e[\udd0d\udd0e\udd10-\udd17\udd20-\udd25\udd27-\udd2f\udd3a\udd3c\udd3f-\udd45\udd47-\udd76\udd78-\uddb4\uddb7\uddba\uddbc-\uddcc\uddd0\uddde-\uddff\ude70-\ude74\ude78-\ude7c\ude80-\ude86\ude90-\udeac\udeb0-\udeba\udec0-\udec2\uded0-\uded9\udee0-\udee7]|[\u23e9-\u23ec\u23f0\u23f3\u267e\u26ce\u2705\u2728\u274c\u274e\u2753-\u2755\u2795-\u2797\u27b0\u27bf\ue50a])|\ufe0f/g,
        UFE0Fg = /\uFE0F/g,
        U200D = String.fromCharCode(8205),
        rescaper = /[&<>'"]/g,
        shouldntBeParsed =
            /^(?:iframe|noframes|noscript|script|select|style|textarea)$/,
        fromCharCode = String.fromCharCode;
    return twemoji;
    function createText(text, clean) {
        return document.createTextNode(clean ? text.replace(UFE0Fg, "") : text);
    }
    function escapeHTML(s) {
        return s.replace(rescaper, replacer);
    }
    function defaultImageSrcGenerator(icon, options) {
        return "".concat(options.base, options.size, "/", icon, options.ext);
    }
    function grabAllTextNodes(node, allText) {
        var childNodes = node.childNodes,
            length = childNodes.length,
            subnode,
            nodeType;
        while (length--) {
            subnode = childNodes[length];
            nodeType = subnode.nodeType;
            if (nodeType === 3) {
                allText.push(subnode);
            } else if (
                nodeType === 1 &&
                !("ownerSVGElement" in subnode) &&
                !shouldntBeParsed.test(subnode.nodeName.toLowerCase())
            ) {
                grabAllTextNodes(subnode, allText);
            }
        }
        return allText;
    }
    function grabTheRightIcon(rawText) {
        return toCodePoint(
            rawText.indexOf(U200D) < 0 ? rawText.replace(UFE0Fg, "") : rawText,
        );
    }
    function parseNode(node, options) {
        var allText = grabAllTextNodes(node, []),
            length = allText.length,
            attrib,
            attrname,
            modified,
            fragment,
            subnode,
            text,
            match,
            i,
            index,
            img,
            rawText,
            iconId,
            src;
        while (length--) {
            modified = false;
            fragment = document.createDocumentFragment();
            subnode = allText[length];
            text = subnode.nodeValue;
            i = 0;
            while ((match = re.exec(text))) {
                index = match.index;
                if (index !== i) {
                    fragment.appendChild(
                        createText(text.slice(i, index), true),
                    );
                }
                rawText = match[0];
                iconId = grabTheRightIcon(rawText);
                i = index + rawText.length;
                src = options.callback(iconId, options);
                if (iconId && src) {
                    img = new Image();
                    img.onerror = options.onerror;
                    img.setAttribute("draggable", "false");
                    attrib = options.attributes(rawText, iconId);
                    for (attrname in attrib) {
                        if (
                            attrib.hasOwnProperty(attrname) &&
                            attrname.indexOf("on") !== 0 &&
                            !img.hasAttribute(attrname)
                        ) {
                            img.setAttribute(attrname, attrib[attrname]);
                        }
                    }
                    img.className = options.className;
                    img.alt = rawText;
                    img.src = src;
                    modified = true;
                    fragment.appendChild(img);
                }
                if (!img) fragment.appendChild(createText(rawText, false));
                img = null;
            }
            if (modified) {
                if (i < text.length) {
                    fragment.appendChild(createText(text.slice(i), true));
                }
                subnode.parentNode.replaceChild(fragment, subnode);
            }
        }
        return node;
    }
    function parseString(str, options) {
        return replace(str, function (rawText) {
            var ret = rawText,
                iconId = grabTheRightIcon(rawText),
                src = options.callback(iconId, options),
                attrib,
                attrname;
            if (iconId && src) {
                ret = "<img ".concat(
                    'class="',
                    options.className,
                    '" ',
                    'draggable="false" ',
                    'alt="',
                    rawText,
                    '"',
                    ' src="',
                    src,
                    '"',
                );
                attrib = options.attributes(rawText, iconId);
                for (attrname in attrib) {
                    if (
                        attrib.hasOwnProperty(attrname) &&
                        attrname.indexOf("on") !== 0 &&
                        ret.indexOf(" " + attrname + "=") === -1
                    ) {
                        ret = ret.concat(
                            " ",
                            attrname,
                            '="',
                            escapeHTML(attrib[attrname]),
                            '"',
                        );
                    }
                }
                ret = ret.concat("/>");
            }
            return ret;
        });
    }
    function replacer(m) {
        return escaper[m];
    }
    function returnNull() {
        return null;
    }
    function toSizeSquaredAsset(value) {
        return typeof value === "number" ? value + "x" + value : value;
    }
    function fromCodePoint(codepoint) {
        var code =
            typeof codepoint === "string" ? parseInt(codepoint, 16) : codepoint;
        if (code < 65536) {
            return fromCharCode(code);
        }
        code -= 65536;
        return fromCharCode(55296 + (code >> 10), 56320 + (code & 1023));
    }
    function parse(what, how) {
        if (!how || typeof how === "function") {
            how = { callback: how };
        }
        return (typeof what === "string" ? parseString : parseNode)(what, {
            callback: how.callback || defaultImageSrcGenerator,
            attributes:
                typeof how.attributes === "function"
                    ? how.attributes
                    : returnNull,
            base: typeof how.base === "string" ? how.base : twemoji.base,
            ext: how.ext || twemoji.ext,
            size: how.folder || toSizeSquaredAsset(how.size || twemoji.size),
            className: how.className || twemoji.className,
            onerror: how.onerror || twemoji.onerror,
        });
    }
    function replace(text, callback) {
        return String(text).replace(re, callback);
    }
    function test(text) {
        re.lastIndex = 0;
        var result = re.test(text);
        re.lastIndex = 0;
        return result;
    }
    function toCodePoint(unicodeSurrogates, sep) {
        var r = [],
            c = 0,
            p = 0,
            i = 0;
        while (i < unicodeSurrogates.length) {
            c = unicodeSurrogates.charCodeAt(i++);
            if (p) {
                r.push(
                    (65536 + ((p - 55296) << 10) + (c - 56320)).toString(16),
                );
                p = 0;
            } else if (55296 <= c && c <= 56319) {
                p = c;
            } else {
                r.push(c.toString(16));
            }
        }
        return r.join(sep || "-");
    }
})();
// XSS过滤
(function () {
    function r(e, n, t) {
        function o(i, f) {
            if (!n[i]) {
                if (!e[i]) {
                    var c = "function" == typeof require && require;
                    if (!f && c) return c(i, !0);
                    if (u) return u(i, !0);
                    var a = new Error("Cannot find module '" + i + "'");
                    throw ((a.code = "MODULE_NOT_FOUND"), a);
                }
                var p = (n[i] = { exports: {} });
                e[i][0].call(
                    p.exports,
                    function (r) {
                        var n = e[i][1][r];
                        return o(n || r);
                    },
                    p,
                    p.exports,
                    r,
                    e,
                    n,
                    t,
                );
            }
            return n[i].exports;
        }
        for (
            var u = "function" == typeof require && require, i = 0;
            i < t.length;
            i++
        )
            o(t[i]);
        return o;
    }
    return r;
})()(
    {
        1: [
            function (require, module, exports) {
                var FilterCSS = require("cssfilter").FilterCSS;
                var getDefaultCSSWhiteList =
                    require("cssfilter").getDefaultWhiteList;
                var _ = require("./util");
                function getDefaultWhiteList() {
                    return {
                        a: ["target", "href", "title"],
                        abbr: ["title"],
                        address: [],
                        area: ["shape", "coords", "href", "alt"],
                        article: [],
                        aside: [],
                        audio: [
                            "autoplay",
                            "controls",
                            "crossorigin",
                            "loop",
                            "muted",
                            "preload",
                            "src",
                        ],
                        b: [],
                        bdi: ["dir"],
                        bdo: ["dir"],
                        big: [],
                        blockquote: ["cite"],
                        br: [],
                        caption: [],
                        center: [],
                        cite: [],
                        code: [],
                        col: ["align", "valign", "span", "width"],
                        colgroup: ["align", "valign", "span", "width"],
                        dd: [],
                        del: ["datetime"],
                        details: ["open"],
                        div: [],
                        dl: [],
                        dt: [],
                        em: [],
                        figcaption: [],
                        figure: [],
                        font: ["color", "size", "face"],
                        footer: [],
                        h1: [],
                        h2: [],
                        h3: [],
                        h4: [],
                        h5: [],
                        h6: [],
                        header: [],
                        hr: [],
                        i: [],
                        img: ["src", "alt", "title", "width", "height"],
                        ins: ["datetime"],
                        li: [],
                        mark: [],
                        nav: [],
                        ol: [],
                        p: [],
                        pre: [],
                        s: [],
                        section: [],
                        small: [],
                        span: [],
                        sub: [],
                        summary: [],
                        sup: [],
                        strong: [],
                        strike: [],
                        table: ["width", "border", "align", "valign"],
                        tbody: ["align", "valign"],
                        td: ["width", "rowspan", "colspan", "align", "valign"],
                        tfoot: ["align", "valign"],
                        th: ["width", "rowspan", "colspan", "align", "valign"],
                        thead: ["align", "valign"],
                        tr: ["rowspan", "align", "valign"],
                        tt: [],
                        u: [],
                        ul: [],
                        video: [
                            "autoplay",
                            "controls",
                            "crossorigin",
                            "loop",
                            "muted",
                            "playsinline",
                            "poster",
                            "preload",
                            "src",
                            "height",
                            "width",
                        ],
                    };
                }
                var defaultCSSFilter = new FilterCSS();
                function onTag(tag, html, options) {}
                function onIgnoreTag(tag, html, options) {}
                function onTagAttr(tag, name, value) {}
                function onIgnoreTagAttr(tag, name, value) {}
                function escapeHtml(html) {
                    return html
                        .replace(REGEXP_LT, "&lt;")
                        .replace(REGEXP_GT, "&gt;");
                }
                function safeAttrValue(tag, name, value, cssFilter) {
                    value = friendlyAttrValue(value);
                    if (name === "href" || name === "src") {
                        value = _.trim(value);
                        if (value === "#") return "#";
                        if (
                            !(
                                value.substr(0, 7) === "http://" ||
                                value.substr(0, 8) === "https://" ||
                                value.substr(0, 7) === "mailto:" ||
                                value.substr(0, 4) === "tel:" ||
                                value.substr(0, 11) === "data:image/" ||
                                value.substr(0, 6) === "ftp://" ||
                                value.substr(0, 2) === "./" ||
                                value.substr(0, 3) === "../" ||
                                value[0] === "#" ||
                                value[0] === "/"
                            )
                        ) {
                            return "";
                        }
                    } else if (name === "background") {
                        REGEXP_DEFAULT_ON_TAG_ATTR_4.lastIndex = 0;
                        if (REGEXP_DEFAULT_ON_TAG_ATTR_4.test(value)) {
                            return "";
                        }
                    } else if (name === "style") {
                        REGEXP_DEFAULT_ON_TAG_ATTR_7.lastIndex = 0;
                        if (REGEXP_DEFAULT_ON_TAG_ATTR_7.test(value)) {
                            return "";
                        }
                        REGEXP_DEFAULT_ON_TAG_ATTR_8.lastIndex = 0;
                        if (REGEXP_DEFAULT_ON_TAG_ATTR_8.test(value)) {
                            REGEXP_DEFAULT_ON_TAG_ATTR_4.lastIndex = 0;
                            if (REGEXP_DEFAULT_ON_TAG_ATTR_4.test(value)) {
                                return "";
                            }
                        }
                        if (cssFilter !== false) {
                            cssFilter = cssFilter || defaultCSSFilter;
                            value = cssFilter.process(value);
                        }
                    }
                    value = escapeAttrValue(value);
                    return value;
                }
                var REGEXP_LT = /</g;
                var REGEXP_GT = />/g;
                var REGEXP_QUOTE = /"/g;
                var REGEXP_QUOTE_2 = /&quot;/g;
                var REGEXP_ATTR_VALUE_1 = /&#([a-zA-Z0-9]*);?/gim;
                var REGEXP_ATTR_VALUE_COLON = /&colon;?/gim;
                var REGEXP_ATTR_VALUE_NEWLINE = /&newline;?/gim;
                var REGEXP_DEFAULT_ON_TAG_ATTR_4 =
                    /((j\s*a\s*v\s*a|v\s*b|l\s*i\s*v\s*e)\s*s\s*c\s*r\s*i\s*p\s*t\s*|m\s*o\s*c\s*h\s*a):/gi;
                var REGEXP_DEFAULT_ON_TAG_ATTR_7 =
                    /e\s*x\s*p\s*r\s*e\s*s\s*s\s*i\s*o\s*n\s*\(.*/gi;
                var REGEXP_DEFAULT_ON_TAG_ATTR_8 = /u\s*r\s*l\s*\(.*/gi;
                function escapeQuote(str) {
                    return str.replace(REGEXP_QUOTE, "&quot;");
                }
                function unescapeQuote(str) {
                    return str.replace(REGEXP_QUOTE_2, '"');
                }
                function escapeHtmlEntities(str) {
                    return str.replace(
                        REGEXP_ATTR_VALUE_1,
                        function replaceUnicode(str, code) {
                            return code[0] === "x" || code[0] === "X"
                                ? String.fromCharCode(
                                      parseInt(code.substr(1), 16),
                                  )
                                : String.fromCharCode(parseInt(code, 10));
                        },
                    );
                }
                function escapeDangerHtml5Entities(str) {
                    return str
                        .replace(REGEXP_ATTR_VALUE_COLON, ":")
                        .replace(REGEXP_ATTR_VALUE_NEWLINE, " ");
                }
                function clearNonPrintableCharacter(str) {
                    var str2 = "";
                    for (var i = 0, len = str.length; i < len; i++) {
                        str2 += str.charCodeAt(i) < 32 ? " " : str.charAt(i);
                    }
                    return _.trim(str2);
                }
                function friendlyAttrValue(str) {
                    str = unescapeQuote(str);
                    str = escapeHtmlEntities(str);
                    str = escapeDangerHtml5Entities(str);
                    str = clearNonPrintableCharacter(str);
                    return str;
                }
                function escapeAttrValue(str) {
                    str = escapeQuote(str);
                    str = escapeHtml(str);
                    return str;
                }
                function onIgnoreTagStripAll() {
                    return "";
                }
                function StripTagBody(tags, next) {
                    if (typeof next !== "function") {
                        next = function () {};
                    }
                    var isRemoveAllTag = !Array.isArray(tags);
                    function isRemoveTag(tag) {
                        if (isRemoveAllTag) return true;
                        return _.indexOf(tags, tag) !== -1;
                    }
                    var removeList = [];
                    var posStart = false;
                    return {
                        onIgnoreTag: function (tag, html, options) {
                            if (isRemoveTag(tag)) {
                                if (options.isClosing) {
                                    var ret = "[/removed]";
                                    var end = options.position + ret.length;
                                    removeList.push([
                                        posStart !== false
                                            ? posStart
                                            : options.position,
                                        end,
                                    ]);
                                    posStart = false;
                                    return ret;
                                } else {
                                    if (!posStart) {
                                        posStart = options.position;
                                    }
                                    return "[removed]";
                                }
                            } else {
                                return next(tag, html, options);
                            }
                        },
                        remove: function (html) {
                            var rethtml = "";
                            var lastPos = 0;
                            _.forEach(removeList, function (pos) {
                                rethtml += html.slice(lastPos, pos[0]);
                                lastPos = pos[1];
                            });
                            rethtml += html.slice(lastPos);
                            return rethtml;
                        },
                    };
                }
                function stripCommentTag(html) {
                    var retHtml = "";
                    var lastPos = 0;
                    while (lastPos < html.length) {
                        var i = html.indexOf("\x3c!--", lastPos);
                        if (i === -1) {
                            retHtml += html.slice(lastPos);
                            break;
                        }
                        retHtml += html.slice(lastPos, i);
                        var j = html.indexOf("--\x3e", i);
                        if (j === -1) {
                            break;
                        }
                        lastPos = j + 3;
                    }
                    return retHtml;
                }
                function stripBlankChar(html) {
                    var chars = html.split("");
                    chars = chars.filter(function (char) {
                        var c = char.charCodeAt(0);
                        if (c === 127) return false;
                        if (c <= 31) {
                            if (c === 10 || c === 13) return true;
                            return false;
                        }
                        return true;
                    });
                    return chars.join("");
                }
                exports.whiteList = getDefaultWhiteList();
                exports.getDefaultWhiteList = getDefaultWhiteList;
                exports.onTag = onTag;
                exports.onIgnoreTag = onIgnoreTag;
                exports.onTagAttr = onTagAttr;
                exports.onIgnoreTagAttr = onIgnoreTagAttr;
                exports.safeAttrValue = safeAttrValue;
                exports.escapeHtml = escapeHtml;
                exports.escapeQuote = escapeQuote;
                exports.unescapeQuote = unescapeQuote;
                exports.escapeHtmlEntities = escapeHtmlEntities;
                exports.escapeDangerHtml5Entities = escapeDangerHtml5Entities;
                exports.clearNonPrintableCharacter = clearNonPrintableCharacter;
                exports.friendlyAttrValue = friendlyAttrValue;
                exports.escapeAttrValue = escapeAttrValue;
                exports.onIgnoreTagStripAll = onIgnoreTagStripAll;
                exports.StripTagBody = StripTagBody;
                exports.stripCommentTag = stripCommentTag;
                exports.stripBlankChar = stripBlankChar;
                exports.cssFilter = defaultCSSFilter;
                exports.getDefaultCSSWhiteList = getDefaultCSSWhiteList;
            },
            { "./util": 4, "cssfilter": 8 },
        ],
        2: [
            function (require, module, exports) {
                var DEFAULT = require("./default");
                var parser = require("./parser");
                var FilterXSS = require("./xss");
                function filterXSS(html, options) {
                    var xss = new FilterXSS(options);
                    return xss.process(html);
                }
                exports = module.exports = filterXSS;
                exports.filterXSS = filterXSS;
                exports.FilterXSS = FilterXSS;
                (function () {
                    for (var i in DEFAULT) {
                        exports[i] = DEFAULT[i];
                    }
                    for (var j in parser) {
                        exports[j] = parser[j];
                    }
                })();
                if (typeof window !== "undefined") {
                    window.filterXSS = module.exports;
                }
                function isWorkerEnv() {
                    return (
                        typeof self !== "undefined" &&
                        typeof DedicatedWorkerGlobalScope !== "undefined" &&
                        self instanceof DedicatedWorkerGlobalScope
                    );
                }
                if (isWorkerEnv()) {
                    self.filterXSS = module.exports;
                }
            },
            { "./default": 1, "./parser": 3, "./xss": 5 },
        ],
        3: [
            function (require, module, exports) {
                var _ = require("./util");
                function getTagName(html) {
                    var i = _.spaceIndex(html);
                    var tagName;
                    if (i === -1) {
                        tagName = html.slice(1, -1);
                    } else {
                        tagName = html.slice(1, i + 1);
                    }
                    tagName = _.trim(tagName).toLowerCase();
                    if (tagName.slice(0, 1) === "/") tagName = tagName.slice(1);
                    if (tagName.slice(-1) === "/")
                        tagName = tagName.slice(0, -1);
                    return tagName;
                }
                function isClosing(html) {
                    return html.slice(0, 2) === "</";
                }
                function parseTag(html, onTag, escapeHtml) {
                    "use strict";
                    var rethtml = "";
                    var lastPos = 0;
                    var tagStart = false;
                    var quoteStart = false;
                    var currentPos = 0;
                    var len = html.length;
                    var currentTagName = "";
                    var currentHtml = "";
                    chariterator: for (
                        currentPos = 0;
                        currentPos < len;
                        currentPos++
                    ) {
                        var c = html.charAt(currentPos);
                        if (tagStart === false) {
                            if (c === "<") {
                                tagStart = currentPos;
                                continue;
                            }
                        } else {
                            if (quoteStart === false) {
                                if (c === "<") {
                                    rethtml += escapeHtml(
                                        html.slice(lastPos, currentPos),
                                    );
                                    tagStart = currentPos;
                                    lastPos = currentPos;
                                    continue;
                                }
                                if (c === ">" || currentPos === len - 1) {
                                    rethtml += escapeHtml(
                                        html.slice(lastPos, tagStart),
                                    );
                                    currentHtml = html.slice(
                                        tagStart,
                                        currentPos + 1,
                                    );
                                    currentTagName = getTagName(currentHtml);
                                    rethtml += onTag(
                                        tagStart,
                                        rethtml.length,
                                        currentTagName,
                                        currentHtml,
                                        isClosing(currentHtml),
                                    );
                                    lastPos = currentPos + 1;
                                    tagStart = false;
                                    continue;
                                }
                                if (c === '"' || c === "'") {
                                    var i = 1;
                                    var ic = html.charAt(currentPos - i);
                                    while (ic.trim() === "" || ic === "=") {
                                        if (ic === "=") {
                                            quoteStart = c;
                                            continue chariterator;
                                        }
                                        ic = html.charAt(currentPos - ++i);
                                    }
                                }
                            } else {
                                if (c === quoteStart) {
                                    quoteStart = false;
                                    continue;
                                }
                            }
                        }
                    }
                    if (lastPos < len) {
                        rethtml += escapeHtml(html.substr(lastPos));
                    }
                    return rethtml;
                }
                var REGEXP_ILLEGAL_ATTR_NAME = /[^a-zA-Z0-9\\_:.-]/gim;
                function parseAttr(html, onAttr) {
                    "use strict";
                    var lastPos = 0;
                    var lastMarkPos = 0;
                    var retAttrs = [];
                    var tmpName = false;
                    var len = html.length;
                    function addAttr(name, value) {
                        name = _.trim(name);
                        name = name
                            .replace(REGEXP_ILLEGAL_ATTR_NAME, "")
                            .toLowerCase();
                        if (name.length < 1) return;
                        var ret = onAttr(name, value || "");
                        if (ret) retAttrs.push(ret);
                    }
                    for (var i = 0; i < len; i++) {
                        var c = html.charAt(i);
                        var v, j;
                        if (tmpName === false && c === "=") {
                            tmpName = html.slice(lastPos, i);
                            lastPos = i + 1;
                            lastMarkPos =
                                html.charAt(lastPos) === '"' ||
                                html.charAt(lastPos) === "'"
                                    ? lastPos
                                    : findNextQuotationMark(html, i + 1);
                            continue;
                        }
                        if (tmpName !== false) {
                            if (i === lastMarkPos) {
                                j = html.indexOf(c, i + 1);
                                if (j === -1) {
                                    break;
                                } else {
                                    v = _.trim(html.slice(lastMarkPos + 1, j));
                                    addAttr(tmpName, v);
                                    tmpName = false;
                                    i = j;
                                    lastPos = i + 1;
                                    continue;
                                }
                            }
                        }
                        if (/\s|\n|\t/.test(c)) {
                            html = html.replace(/\s|\n|\t/g, " ");
                            if (tmpName === false) {
                                j = findNextEqual(html, i);
                                if (j === -1) {
                                    v = _.trim(html.slice(lastPos, i));
                                    addAttr(v);
                                    tmpName = false;
                                    lastPos = i + 1;
                                    continue;
                                } else {
                                    i = j - 1;
                                    continue;
                                }
                            } else {
                                j = findBeforeEqual(html, i - 1);
                                if (j === -1) {
                                    v = _.trim(html.slice(lastPos, i));
                                    v = stripQuoteWrap(v);
                                    addAttr(tmpName, v);
                                    tmpName = false;
                                    lastPos = i + 1;
                                    continue;
                                } else {
                                    continue;
                                }
                            }
                        }
                    }
                    if (lastPos < html.length) {
                        if (tmpName === false) {
                            addAttr(html.slice(lastPos));
                        } else {
                            addAttr(
                                tmpName,
                                stripQuoteWrap(_.trim(html.slice(lastPos))),
                            );
                        }
                    }
                    return _.trim(retAttrs.join(" "));
                }
                function findNextEqual(str, i) {
                    for (; i < str.length; i++) {
                        var c = str[i];
                        if (c === " ") continue;
                        if (c === "=") return i;
                        return -1;
                    }
                }
                function findNextQuotationMark(str, i) {
                    for (; i < str.length; i++) {
                        var c = str[i];
                        if (c === " ") continue;
                        if (c === "'" || c === '"') return i;
                        return -1;
                    }
                }
                function findBeforeEqual(str, i) {
                    for (; i > 0; i--) {
                        var c = str[i];
                        if (c === " ") continue;
                        if (c === "=") return i;
                        return -1;
                    }
                }
                function isQuoteWrapString(text) {
                    if (
                        (text[0] === '"' && text[text.length - 1] === '"') ||
                        (text[0] === "'" && text[text.length - 1] === "'")
                    ) {
                        return true;
                    } else {
                        return false;
                    }
                }
                function stripQuoteWrap(text) {
                    if (isQuoteWrapString(text)) {
                        return text.substr(1, text.length - 2);
                    } else {
                        return text;
                    }
                }
                exports.parseTag = parseTag;
                exports.parseAttr = parseAttr;
            },
            { "./util": 4 },
        ],
        4: [
            function (require, module, exports) {
                module.exports = {
                    indexOf: function (arr, item) {
                        var i, j;
                        if (Array.prototype.indexOf) {
                            return arr.indexOf(item);
                        }
                        for (i = 0, j = arr.length; i < j; i++) {
                            if (arr[i] === item) {
                                return i;
                            }
                        }
                        return -1;
                    },
                    forEach: function (arr, fn, scope) {
                        var i, j;
                        if (Array.prototype.forEach) {
                            return arr.forEach(fn, scope);
                        }
                        for (i = 0, j = arr.length; i < j; i++) {
                            fn.call(scope, arr[i], i, arr);
                        }
                    },
                    trim: function (str) {
                        if (String.prototype.trim) {
                            return str.trim();
                        }
                        return str.replace(/(^\s*)|(\s*$)/g, "");
                    },
                    spaceIndex: function (str) {
                        var reg = /\s|\n|\t/;
                        var match = reg.exec(str);
                        return match ? match.index : -1;
                    },
                };
            },
            {},
        ],
        5: [
            function (require, module, exports) {
                var FilterCSS = require("cssfilter").FilterCSS;
                var DEFAULT = require("./default");
                var parser = require("./parser");
                var parseTag = parser.parseTag;
                var parseAttr = parser.parseAttr;
                var _ = require("./util");
                function isNull(obj) {
                    return obj === undefined || obj === null;
                }
                function getAttrs(html) {
                    var i = _.spaceIndex(html);
                    if (i === -1) {
                        return {
                            html: "",
                            closing: html[html.length - 2] === "/",
                        };
                    }
                    html = _.trim(html.slice(i + 1, -1));
                    var isClosing = html[html.length - 1] === "/";
                    if (isClosing) html = _.trim(html.slice(0, -1));
                    return { html: html, closing: isClosing };
                }
                function shallowCopyObject(obj) {
                    var ret = {};
                    for (var i in obj) {
                        ret[i] = obj[i];
                    }
                    return ret;
                }
                function keysToLowerCase(obj) {
                    var ret = {};
                    for (var i in obj) {
                        if (Array.isArray(obj[i])) {
                            ret[i.toLowerCase()] = obj[i].map(function (item) {
                                return item.toLowerCase();
                            });
                        } else {
                            ret[i.toLowerCase()] = obj[i];
                        }
                    }
                    return ret;
                }
                function FilterXSS(options) {
                    options = shallowCopyObject(options || {});
                    if (options.stripIgnoreTag) {
                        if (options.onIgnoreTag) {
                            console.error(
                                'Notes: cannot use these two options "stripIgnoreTag" and "onIgnoreTag" at the same time',
                            );
                        }
                        options.onIgnoreTag = DEFAULT.onIgnoreTagStripAll;
                    }
                    if (options.whiteList || options.allowList) {
                        options.whiteList = keysToLowerCase(
                            options.whiteList || options.allowList,
                        );
                    } else {
                        options.whiteList = DEFAULT.whiteList;
                    }
                    options.onTag = options.onTag || DEFAULT.onTag;
                    options.onTagAttr = options.onTagAttr || DEFAULT.onTagAttr;
                    options.onIgnoreTag =
                        options.onIgnoreTag || DEFAULT.onIgnoreTag;
                    options.onIgnoreTagAttr =
                        options.onIgnoreTagAttr || DEFAULT.onIgnoreTagAttr;
                    options.safeAttrValue =
                        options.safeAttrValue || DEFAULT.safeAttrValue;
                    options.escapeHtml =
                        options.escapeHtml || DEFAULT.escapeHtml;
                    this.options = options;
                    if (options.css === false) {
                        this.cssFilter = false;
                    } else {
                        options.css = options.css || {};
                        this.cssFilter = new FilterCSS(options.css);
                    }
                }
                FilterXSS.prototype.process = function (html) {
                    html = html || "";
                    html = html.toString();
                    if (!html) return "";
                    var me = this;
                    var options = me.options;
                    var whiteList = options.whiteList;
                    var onTag = options.onTag;
                    var onIgnoreTag = options.onIgnoreTag;
                    var onTagAttr = options.onTagAttr;
                    var onIgnoreTagAttr = options.onIgnoreTagAttr;
                    var safeAttrValue = options.safeAttrValue;
                    var escapeHtml = options.escapeHtml;
                    var cssFilter = me.cssFilter;
                    if (options.stripBlankChar) {
                        html = DEFAULT.stripBlankChar(html);
                    }
                    if (!options.allowCommentTag) {
                        html = DEFAULT.stripCommentTag(html);
                    }
                    var stripIgnoreTagBody = false;
                    if (options.stripIgnoreTagBody) {
                        stripIgnoreTagBody = DEFAULT.StripTagBody(
                            options.stripIgnoreTagBody,
                            onIgnoreTag,
                        );
                        onIgnoreTag = stripIgnoreTagBody.onIgnoreTag;
                    }
                    var retHtml = parseTag(
                        html,
                        function (
                            sourcePosition,
                            position,
                            tag,
                            html,
                            isClosing,
                        ) {
                            var info = {
                                sourcePosition: sourcePosition,
                                position: position,
                                isClosing: isClosing,
                                isWhite: Object.prototype.hasOwnProperty.call(
                                    whiteList,
                                    tag,
                                ),
                            };
                            var ret = onTag(tag, html, info);
                            if (!isNull(ret)) return ret;
                            if (info.isWhite) {
                                if (info.isClosing) {
                                    return "</" + tag + ">";
                                }
                                var attrs = getAttrs(html);
                                var whiteAttrList = whiteList[tag];
                                var attrsHtml = parseAttr(
                                    attrs.html,
                                    function (name, value) {
                                        var isWhiteAttr =
                                            _.indexOf(whiteAttrList, name) !==
                                            -1;
                                        var ret = onTagAttr(
                                            tag,
                                            name,
                                            value,
                                            isWhiteAttr,
                                        );
                                        if (!isNull(ret)) return ret;
                                        if (isWhiteAttr) {
                                            value = safeAttrValue(
                                                tag,
                                                name,
                                                value,
                                                cssFilter,
                                            );
                                            if (value) {
                                                return (
                                                    name + '="' + value + '"'
                                                );
                                            } else {
                                                return name;
                                            }
                                        } else {
                                            ret = onIgnoreTagAttr(
                                                tag,
                                                name,
                                                value,
                                                isWhiteAttr,
                                            );
                                            if (!isNull(ret)) return ret;
                                            return;
                                        }
                                    },
                                );
                                html = "<" + tag;
                                if (attrsHtml) html += " " + attrsHtml;
                                if (attrs.closing) html += " /";
                                html += ">";
                                return html;
                            } else {
                                ret = onIgnoreTag(tag, html, info);
                                if (!isNull(ret)) return ret;
                                return escapeHtml(html);
                            }
                        },
                        escapeHtml,
                    );
                    if (stripIgnoreTagBody) {
                        retHtml = stripIgnoreTagBody.remove(retHtml);
                    }
                    return retHtml;
                };
                module.exports = FilterXSS;
            },
            { "./default": 1, "./parser": 3, "./util": 4, "cssfilter": 8 },
        ],
        6: [
            function (require, module, exports) {
                var DEFAULT = require("./default");
                var parseStyle = require("./parser");
                var _ = require("./util");
                function isNull(obj) {
                    return obj === undefined || obj === null;
                }
                function shallowCopyObject(obj) {
                    var ret = {};
                    for (var i in obj) {
                        ret[i] = obj[i];
                    }
                    return ret;
                }
                function FilterCSS(options) {
                    options = shallowCopyObject(options || {});
                    options.whiteList = options.whiteList || DEFAULT.whiteList;
                    options.onAttr = options.onAttr || DEFAULT.onAttr;
                    options.onIgnoreAttr =
                        options.onIgnoreAttr || DEFAULT.onIgnoreAttr;
                    options.safeAttrValue =
                        options.safeAttrValue || DEFAULT.safeAttrValue;
                    this.options = options;
                }
                FilterCSS.prototype.process = function (css) {
                    css = css || "";
                    css = css.toString();
                    if (!css) return "";
                    var me = this;
                    var options = me.options;
                    var whiteList = options.whiteList;
                    var onAttr = options.onAttr;
                    var onIgnoreAttr = options.onIgnoreAttr;
                    var safeAttrValue = options.safeAttrValue;
                    var retCSS = parseStyle(
                        css,
                        function (
                            sourcePosition,
                            position,
                            name,
                            value,
                            source,
                        ) {
                            var check = whiteList[name];
                            var isWhite = false;
                            if (check === true) isWhite = check;
                            else if (typeof check === "function")
                                isWhite = check(value);
                            else if (check instanceof RegExp)
                                isWhite = check.test(value);
                            if (isWhite !== true) isWhite = false;
                            value = safeAttrValue(name, value);
                            if (!value) return;
                            var opts = {
                                position: position,
                                sourcePosition: sourcePosition,
                                source: source,
                                isWhite: isWhite,
                            };
                            if (isWhite) {
                                var ret = onAttr(name, value, opts);
                                if (isNull(ret)) {
                                    return name + ":" + value;
                                } else {
                                    return ret;
                                }
                            } else {
                                var ret = onIgnoreAttr(name, value, opts);
                                if (!isNull(ret)) {
                                    return ret;
                                }
                            }
                        },
                    );
                    return retCSS;
                };
                module.exports = FilterCSS;
            },
            { "./default": 7, "./parser": 9, "./util": 10 },
        ],
        7: [
            function (require, module, exports) {
                function getDefaultWhiteList() {
                    var whiteList = {};
                    whiteList["align-content"] = false;
                    whiteList["align-items"] = false;
                    whiteList["align-self"] = false;
                    whiteList["alignment-adjust"] = false;
                    whiteList["alignment-baseline"] = false;
                    whiteList["all"] = false;
                    whiteList["anchor-point"] = false;
                    whiteList["animation"] = false;
                    whiteList["animation-delay"] = false;
                    whiteList["animation-direction"] = false;
                    whiteList["animation-duration"] = false;
                    whiteList["animation-fill-mode"] = false;
                    whiteList["animation-iteration-count"] = false;
                    whiteList["animation-name"] = false;
                    whiteList["animation-play-state"] = false;
                    whiteList["animation-timing-function"] = false;
                    whiteList["azimuth"] = false;
                    whiteList["backface-visibility"] = false;
                    whiteList["background"] = true;
                    whiteList["background-attachment"] = true;
                    whiteList["background-clip"] = true;
                    whiteList["background-color"] = true;
                    whiteList["background-image"] = true;
                    whiteList["background-origin"] = true;
                    whiteList["background-position"] = true;
                    whiteList["background-repeat"] = true;
                    whiteList["background-size"] = true;
                    whiteList["baseline-shift"] = false;
                    whiteList["binding"] = false;
                    whiteList["bleed"] = false;
                    whiteList["bookmark-label"] = false;
                    whiteList["bookmark-level"] = false;
                    whiteList["bookmark-state"] = false;
                    whiteList["border"] = true;
                    whiteList["border-bottom"] = true;
                    whiteList["border-bottom-color"] = true;
                    whiteList["border-bottom-left-radius"] = true;
                    whiteList["border-bottom-right-radius"] = true;
                    whiteList["border-bottom-style"] = true;
                    whiteList["border-bottom-width"] = true;
                    whiteList["border-collapse"] = true;
                    whiteList["border-color"] = true;
                    whiteList["border-image"] = true;
                    whiteList["border-image-outset"] = true;
                    whiteList["border-image-repeat"] = true;
                    whiteList["border-image-slice"] = true;
                    whiteList["border-image-source"] = true;
                    whiteList["border-image-width"] = true;
                    whiteList["border-left"] = true;
                    whiteList["border-left-color"] = true;
                    whiteList["border-left-style"] = true;
                    whiteList["border-left-width"] = true;
                    whiteList["border-radius"] = true;
                    whiteList["border-right"] = true;
                    whiteList["border-right-color"] = true;
                    whiteList["border-right-style"] = true;
                    whiteList["border-right-width"] = true;
                    whiteList["border-spacing"] = true;
                    whiteList["border-style"] = true;
                    whiteList["border-top"] = true;
                    whiteList["border-top-color"] = true;
                    whiteList["border-top-left-radius"] = true;
                    whiteList["border-top-right-radius"] = true;
                    whiteList["border-top-style"] = true;
                    whiteList["border-top-width"] = true;
                    whiteList["border-width"] = true;
                    whiteList["bottom"] = false;
                    whiteList["box-decoration-break"] = true;
                    whiteList["box-shadow"] = true;
                    whiteList["box-sizing"] = true;
                    whiteList["box-snap"] = true;
                    whiteList["box-suppress"] = true;
                    whiteList["break-after"] = true;
                    whiteList["break-before"] = true;
                    whiteList["break-inside"] = true;
                    whiteList["caption-side"] = false;
                    whiteList["chains"] = false;
                    whiteList["clear"] = true;
                    whiteList["clip"] = false;
                    whiteList["clip-path"] = false;
                    whiteList["clip-rule"] = false;
                    whiteList["color"] = true;
                    whiteList["color-interpolation-filters"] = true;
                    whiteList["column-count"] = false;
                    whiteList["column-fill"] = false;
                    whiteList["column-gap"] = false;
                    whiteList["column-rule"] = false;
                    whiteList["column-rule-color"] = false;
                    whiteList["column-rule-style"] = false;
                    whiteList["column-rule-width"] = false;
                    whiteList["column-span"] = false;
                    whiteList["column-width"] = false;
                    whiteList["columns"] = false;
                    whiteList["contain"] = false;
                    whiteList["content"] = false;
                    whiteList["counter-increment"] = false;
                    whiteList["counter-reset"] = false;
                    whiteList["counter-set"] = false;
                    whiteList["crop"] = false;
                    whiteList["cue"] = false;
                    whiteList["cue-after"] = false;
                    whiteList["cue-before"] = false;
                    whiteList["cursor"] = false;
                    whiteList["direction"] = false;
                    whiteList["display"] = true;
                    whiteList["display-inside"] = true;
                    whiteList["display-list"] = true;
                    whiteList["display-outside"] = true;
                    whiteList["dominant-baseline"] = false;
                    whiteList["elevation"] = false;
                    whiteList["empty-cells"] = false;
                    whiteList["filter"] = false;
                    whiteList["flex"] = false;
                    whiteList["flex-basis"] = false;
                    whiteList["flex-direction"] = false;
                    whiteList["flex-flow"] = false;
                    whiteList["flex-grow"] = false;
                    whiteList["flex-shrink"] = false;
                    whiteList["flex-wrap"] = false;
                    whiteList["float"] = false;
                    whiteList["float-offset"] = false;
                    whiteList["flood-color"] = false;
                    whiteList["flood-opacity"] = false;
                    whiteList["flow-from"] = false;
                    whiteList["flow-into"] = false;
                    whiteList["font"] = true;
                    whiteList["font-family"] = true;
                    whiteList["font-feature-settings"] = true;
                    whiteList["font-kerning"] = true;
                    whiteList["font-language-override"] = true;
                    whiteList["font-size"] = true;
                    whiteList["font-size-adjust"] = true;
                    whiteList["font-stretch"] = true;
                    whiteList["font-style"] = true;
                    whiteList["font-synthesis"] = true;
                    whiteList["font-variant"] = true;
                    whiteList["font-variant-alternates"] = true;
                    whiteList["font-variant-caps"] = true;
                    whiteList["font-variant-east-asian"] = true;
                    whiteList["font-variant-ligatures"] = true;
                    whiteList["font-variant-numeric"] = true;
                    whiteList["font-variant-position"] = true;
                    whiteList["font-weight"] = true;
                    whiteList["grid"] = false;
                    whiteList["grid-area"] = false;
                    whiteList["grid-auto-columns"] = false;
                    whiteList["grid-auto-flow"] = false;
                    whiteList["grid-auto-rows"] = false;
                    whiteList["grid-column"] = false;
                    whiteList["grid-column-end"] = false;
                    whiteList["grid-column-start"] = false;
                    whiteList["grid-row"] = false;
                    whiteList["grid-row-end"] = false;
                    whiteList["grid-row-start"] = false;
                    whiteList["grid-template"] = false;
                    whiteList["grid-template-areas"] = false;
                    whiteList["grid-template-columns"] = false;
                    whiteList["grid-template-rows"] = false;
                    whiteList["hanging-punctuation"] = false;
                    whiteList["height"] = true;
                    whiteList["hyphens"] = false;
                    whiteList["icon"] = false;
                    whiteList["image-orientation"] = false;
                    whiteList["image-resolution"] = false;
                    whiteList["ime-mode"] = false;
                    whiteList["initial-letters"] = false;
                    whiteList["inline-box-align"] = false;
                    whiteList["justify-content"] = false;
                    whiteList["justify-items"] = false;
                    whiteList["justify-self"] = false;
                    whiteList["left"] = false;
                    whiteList["letter-spacing"] = true;
                    whiteList["lighting-color"] = true;
                    whiteList["line-box-contain"] = false;
                    whiteList["line-break"] = false;
                    whiteList["line-grid"] = false;
                    whiteList["line-height"] = false;
                    whiteList["line-snap"] = false;
                    whiteList["line-stacking"] = false;
                    whiteList["line-stacking-ruby"] = false;
                    whiteList["line-stacking-shift"] = false;
                    whiteList["line-stacking-strategy"] = false;
                    whiteList["list-style"] = true;
                    whiteList["list-style-image"] = true;
                    whiteList["list-style-position"] = true;
                    whiteList["list-style-type"] = true;
                    whiteList["margin"] = true;
                    whiteList["margin-bottom"] = true;
                    whiteList["margin-left"] = true;
                    whiteList["margin-right"] = true;
                    whiteList["margin-top"] = true;
                    whiteList["marker-offset"] = false;
                    whiteList["marker-side"] = false;
                    whiteList["marks"] = false;
                    whiteList["mask"] = false;
                    whiteList["mask-box"] = false;
                    whiteList["mask-box-outset"] = false;
                    whiteList["mask-box-repeat"] = false;
                    whiteList["mask-box-slice"] = false;
                    whiteList["mask-box-source"] = false;
                    whiteList["mask-box-width"] = false;
                    whiteList["mask-clip"] = false;
                    whiteList["mask-image"] = false;
                    whiteList["mask-origin"] = false;
                    whiteList["mask-position"] = false;
                    whiteList["mask-repeat"] = false;
                    whiteList["mask-size"] = false;
                    whiteList["mask-source-type"] = false;
                    whiteList["mask-type"] = false;
                    whiteList["max-height"] = true;
                    whiteList["max-lines"] = false;
                    whiteList["max-width"] = true;
                    whiteList["min-height"] = true;
                    whiteList["min-width"] = true;
                    whiteList["move-to"] = false;
                    whiteList["nav-down"] = false;
                    whiteList["nav-index"] = false;
                    whiteList["nav-left"] = false;
                    whiteList["nav-right"] = false;
                    whiteList["nav-up"] = false;
                    whiteList["object-fit"] = false;
                    whiteList["object-position"] = false;
                    whiteList["opacity"] = false;
                    whiteList["order"] = false;
                    whiteList["orphans"] = false;
                    whiteList["outline"] = false;
                    whiteList["outline-color"] = false;
                    whiteList["outline-offset"] = false;
                    whiteList["outline-style"] = false;
                    whiteList["outline-width"] = false;
                    whiteList["overflow"] = false;
                    whiteList["overflow-wrap"] = false;
                    whiteList["overflow-x"] = false;
                    whiteList["overflow-y"] = false;
                    whiteList["padding"] = true;
                    whiteList["padding-bottom"] = true;
                    whiteList["padding-left"] = true;
                    whiteList["padding-right"] = true;
                    whiteList["padding-top"] = true;
                    whiteList["page"] = false;
                    whiteList["page-break-after"] = false;
                    whiteList["page-break-before"] = false;
                    whiteList["page-break-inside"] = false;
                    whiteList["page-policy"] = false;
                    whiteList["pause"] = false;
                    whiteList["pause-after"] = false;
                    whiteList["pause-before"] = false;
                    whiteList["perspective"] = false;
                    whiteList["perspective-origin"] = false;
                    whiteList["pitch"] = false;
                    whiteList["pitch-range"] = false;
                    whiteList["play-during"] = false;
                    whiteList["position"] = false;
                    whiteList["presentation-level"] = false;
                    whiteList["quotes"] = false;
                    whiteList["region-fragment"] = false;
                    whiteList["resize"] = false;
                    whiteList["rest"] = false;
                    whiteList["rest-after"] = false;
                    whiteList["rest-before"] = false;
                    whiteList["richness"] = false;
                    whiteList["right"] = false;
                    whiteList["rotation"] = false;
                    whiteList["rotation-point"] = false;
                    whiteList["ruby-align"] = false;
                    whiteList["ruby-merge"] = false;
                    whiteList["ruby-position"] = false;
                    whiteList["shape-image-threshold"] = false;
                    whiteList["shape-outside"] = false;
                    whiteList["shape-margin"] = false;
                    whiteList["size"] = false;
                    whiteList["speak"] = false;
                    whiteList["speak-as"] = false;
                    whiteList["speak-header"] = false;
                    whiteList["speak-numeral"] = false;
                    whiteList["speak-punctuation"] = false;
                    whiteList["speech-rate"] = false;
                    whiteList["stress"] = false;
                    whiteList["string-set"] = false;
                    whiteList["tab-size"] = false;
                    whiteList["table-layout"] = false;
                    whiteList["text-align"] = true;
                    whiteList["text-align-last"] = true;
                    whiteList["text-combine-upright"] = true;
                    whiteList["text-decoration"] = true;
                    whiteList["text-decoration-color"] = true;
                    whiteList["text-decoration-line"] = true;
                    whiteList["text-decoration-skip"] = true;
                    whiteList["text-decoration-style"] = true;
                    whiteList["text-emphasis"] = true;
                    whiteList["text-emphasis-color"] = true;
                    whiteList["text-emphasis-position"] = true;
                    whiteList["text-emphasis-style"] = true;
                    whiteList["text-height"] = true;
                    whiteList["text-indent"] = true;
                    whiteList["text-justify"] = true;
                    whiteList["text-orientation"] = true;
                    whiteList["text-overflow"] = true;
                    whiteList["text-shadow"] = true;
                    whiteList["text-space-collapse"] = true;
                    whiteList["text-transform"] = true;
                    whiteList["text-underline-position"] = true;
                    whiteList["text-wrap"] = true;
                    whiteList["top"] = false;
                    whiteList["transform"] = false;
                    whiteList["transform-origin"] = false;
                    whiteList["transform-style"] = false;
                    whiteList["transition"] = false;
                    whiteList["transition-delay"] = false;
                    whiteList["transition-duration"] = false;
                    whiteList["transition-property"] = false;
                    whiteList["transition-timing-function"] = false;
                    whiteList["unicode-bidi"] = false;
                    whiteList["vertical-align"] = false;
                    whiteList["visibility"] = false;
                    whiteList["voice-balance"] = false;
                    whiteList["voice-duration"] = false;
                    whiteList["voice-family"] = false;
                    whiteList["voice-pitch"] = false;
                    whiteList["voice-range"] = false;
                    whiteList["voice-rate"] = false;
                    whiteList["voice-stress"] = false;
                    whiteList["voice-volume"] = false;
                    whiteList["volume"] = false;
                    whiteList["white-space"] = false;
                    whiteList["widows"] = false;
                    whiteList["width"] = true;
                    whiteList["will-change"] = false;
                    whiteList["word-break"] = true;
                    whiteList["word-spacing"] = true;
                    whiteList["word-wrap"] = true;
                    whiteList["wrap-flow"] = false;
                    whiteList["wrap-through"] = false;
                    whiteList["writing-mode"] = false;
                    whiteList["z-index"] = false;
                    return whiteList;
                }
                function onAttr(name, value, options) {}
                function onIgnoreAttr(name, value, options) {}
                var REGEXP_URL_JAVASCRIPT = /javascript\s*\:/gim;
                function safeAttrValue(name, value) {
                    if (REGEXP_URL_JAVASCRIPT.test(value)) return "";
                    return value;
                }
                exports.whiteList = getDefaultWhiteList();
                exports.getDefaultWhiteList = getDefaultWhiteList;
                exports.onAttr = onAttr;
                exports.onIgnoreAttr = onIgnoreAttr;
                exports.safeAttrValue = safeAttrValue;
            },
            {},
        ],
        8: [
            function (require, module, exports) {
                var DEFAULT = require("./default");
                var FilterCSS = require("./css");
                function filterCSS(html, options) {
                    var xss = new FilterCSS(options);
                    return xss.process(html);
                }
                exports = module.exports = filterCSS;
                exports.FilterCSS = FilterCSS;
                for (var i in DEFAULT) exports[i] = DEFAULT[i];
                if (typeof window !== "undefined") {
                    window.filterCSS = module.exports;
                }
            },
            { "./css": 6, "./default": 7 },
        ],
        9: [
            function (require, module, exports) {
                var _ = require("./util");
                function parseStyle(css, onAttr) {
                    css = _.trimRight(css);
                    if (css[css.length - 1] !== ";") css += ";";
                    var cssLength = css.length;
                    var isParenthesisOpen = false;
                    var lastPos = 0;
                    var i = 0;
                    var retCSS = "";
                    function addNewAttr() {
                        if (!isParenthesisOpen) {
                            var source = _.trim(css.slice(lastPos, i));
                            var j = source.indexOf(":");
                            if (j !== -1) {
                                var name = _.trim(source.slice(0, j));
                                var value = _.trim(source.slice(j + 1));
                                if (name) {
                                    var ret = onAttr(
                                        lastPos,
                                        retCSS.length,
                                        name,
                                        value,
                                        source,
                                    );
                                    if (ret) retCSS += ret + "; ";
                                }
                            }
                        }
                        lastPos = i + 1;
                    }
                    for (; i < cssLength; i++) {
                        var c = css[i];
                        if (c === "/" && css[i + 1] === "*") {
                            var j = css.indexOf("*/", i + 2);
                            if (j === -1) break;
                            i = j + 1;
                            lastPos = i + 1;
                            isParenthesisOpen = false;
                        } else if (c === "(") {
                            isParenthesisOpen = true;
                        } else if (c === ")") {
                            isParenthesisOpen = false;
                        } else if (c === ";") {
                            if (isParenthesisOpen) {
                            } else {
                                addNewAttr();
                            }
                        } else if (c === "\n") {
                            addNewAttr();
                        }
                    }
                    return _.trim(retCSS);
                }
                module.exports = parseStyle;
            },
            { "./util": 10 },
        ],
        10: [
            function (require, module, exports) {
                module.exports = {
                    indexOf: function (arr, item) {
                        var i, j;
                        if (Array.prototype.indexOf) {
                            return arr.indexOf(item);
                        }
                        for (i = 0, j = arr.length; i < j; i++) {
                            if (arr[i] === item) {
                                return i;
                            }
                        }
                        return -1;
                    },
                    forEach: function (arr, fn, scope) {
                        var i, j;
                        if (Array.prototype.forEach) {
                            return arr.forEach(fn, scope);
                        }
                        for (i = 0, j = arr.length; i < j; i++) {
                            fn.call(scope, arr[i], i, arr);
                        }
                    },
                    trim: function (str) {
                        if (String.prototype.trim) {
                            return str.trim();
                        }
                        return str.replace(/(^\s*)|(\s*$)/g, "");
                    },
                    trimRight: function (str) {
                        if (String.prototype.trimRight) {
                            return str.trimRight();
                        }
                        return str.replace(/(\s*$)/g, "");
                    },
                };
            },
            {},
        ],
    },
    {},
    [2],
);

// 外部参数
var GLOBAL_TOOL = (typeof playwright_config != "undefined" &&
    playwright_config) || {
    ENABLE_PLAYWRIGHT: false, // playwright 支持
};

(function () {
    "use strict";
    /**
     * 烤推核心
     */
    const LOG_LEVELS = {
        NORMAL: 0,
        ERROR: 1,
        EXCEPTION: 2,
        WARNING: 3,
        INFO: 4,
        DEBUG: 5,
    };
    // 核心配置
    const CONFIG_CORE = {
        LOG_OUT: console.log, // 使用的日志输出（可空）
        START_WAIT_TIME: 20, // 启动等待时间
        RUN_MAIN: true, // 是否运行主函数，不运行主函数的情况下不会自动执行任何操作
        AUTO_LOAD: true, // 是否启用自动解析加载
        UI_ENALBE: false, // 是否启用UI支持
        SHOW_HIDE: true, // 是否在等待中包含 解锁隐藏
        URL_CHECK_ENALBE: false, // 是否启用URL切换检测
        LOG_LEVEL: LOG_LEVELS.DEBUG, // 日志等级
    };
    // 静态变量配置
    const CONST_VAL = {
        static_elem_id: "static_elem", // 静态烤推主元素的ID
        static_mark_hide: "static_hide_trans", // 元素隐藏标识类，用于标识被隐藏的类
        static_insert_trans: "static_insert_trans", // 注入元素的标记，烤推模版烤推内容均包含在其中
        static_insert_tran_text: "insert_trans_text", // 翻译文本
        static_insert_tran_type: "insert_trans_type", // 翻译标识
        static_insert_tran_media: "insert_trans_media", // 媒体
        static_insert_tran_vote: "insert_trans_vote", // 投票
        // 样式常量
        tran_main_style:
            'font-family: "Source Han Sans CN", "Segoe UI", Meiryo, system-ui, -apple-system, BlinkMacSystemFont, sans-serif;',
        tran_text_style: "font-size: 0.9em;",
        tran_type_style:
            "color: #1DA1F2;font-size: 0.8em;font-weight: 500;padding: 0.3em 0 0.3em 5px;",
        tran_media_style: "",
        tran_vote_style: "",
    };

    // 烤推核心配置
    // 页面锚点(样式检索点配置)
    const CSSAnchor = {
        // 根元素锚点
        rootElem(rootDom = document) {
            return rootDom.querySelector(
                "section[aria-labelledby].css-1dbjc4n",
            );
        },
        // 推文集锚点
        articles(rootDom) {
            return rootDom.querySelectorAll("ARTICLE.css-1dbjc4n");
        },
        // 敏感内容锚点
        articleHides(rootDom) {
            return rootDom.querySelectorAll("DIV.r-1ndi9ce div[role='button']");
        },
        // 媒体锚点
        articleVideo(rootDom) {
            return rootDom.querySelectorAll("video[poster]");
        },
        // 任意推文图片锚点（与articleInImage合用）
        articleImages(rootDom) {
            return rootDom.querySelectorAll('a[href*="/photo/"]');
        },
        // 图文描点内联的IMG
        articleInImage(rootDom) {
            return rootDom.querySelector('img[src*="/media/"]');
        },
        // 文本锚点
        articleTexts(rootDom) {
            // DIV.r-bnwqim
            // return rootDom.querySelectorAll("div.r-bnwqim");
            return rootDom.querySelectorAll("div[data-testid=tweetText]");
        },
        // 投票锚点
        articleVotes(rootDom) {
            // // 已经结束的投票
            // let res = rootDom.querySelectorAll(
            //     "DIV.r-mabqd8 DIV.r-1e081e0"
            // );
            // if (res.length != 0) {
            //     return res;
            // }
            // // 未结束的投票
            // return rootDom.querySelectorAll("DIV.r-p1n3y5 SPAN.css-bfa6kz");
            let pollDom = rootDom.querySelector("div[data-testid=cardPoll]");
            if (!pollDom) {
                return [];
            }
            let pollItemDom = pollDom.querySelectorAll(
                "div[role=radio] div>span",
            );
            if (pollItemDom.length == 0) {
                // 认为是投票已经结束的情况
                try {
                    let tmpDoms = pollDom.querySelectorAll("li");
                    pollItemDom = [];
                    for (let i = 0; i < tmpDoms.length; i++) {
                        pollItemDom.push(
                            tmpDoms[i].querySelectorAll("span")[0],
                        );
                    }
                } catch (e) {
                    Logger.debug(e);
                    return [];
                }
            }
            return pollItemDom;
        },
        // 转推喜欢检索锚点
        articleRetweetLike(rootDom) {
            // r-tzz3ar r-1yzf0co
            return rootDom.querySelector("div.r-tzz3ar");
        },
        // 时间锚点
        articleTime(rootDom) {
            return rootDom.querySelector("div.r-1r5su4o");
        },
        // 翻译锚点
        transNotice(rootDom) {
            return rootDom.querySelector("DIV.r-1w6e6rj");
        },
        // 弹框锚点(登录提示框)
        twitterDialog() {
            return document.querySelector("div[role=dialog]");
        },
        // 底部登录栏
        twitterBottomBar() {
            return document.querySelector("div[data-testid=BottomBar]");
        },
        // 报错检查
        twitterError() {
            let dom = document.querySelector(
                "div[data-testid=error-detail] DIV>span",
            );
            if (!dom) {
                dom = document.querySelector("DIV.r-tvv088 DIV.r-117bsoe SPAN");
            }
            return dom;
        },
        // 需要等待的元素
        twitterNeedWait() {
            let dom = document.querySelector("[role=progressbar]");
            return dom;
        },
    };

    // 日志
    const Logger = {};
    (function () {
        // 核心输出函数
        var log = console.log;
        if (typeof GM_log != "undefined") {
            log = GM_log;
        }
        if (CONFIG_CORE.LOG_OUT) {
            log = CONFIG_CORE.LOG_OUT;
        }
        Logger.LEVEL = 5;
        Logger.LEVELSTRS = [
            "",
            "[错误]",
            "[异常]",
            "[警告]",
            "[信息]",
            "[调试]",
        ];
        Logger.LEVELS = LOG_LEVELS;
        Logger.out = function (msg, level = Logger.LEVELS.NORMAL, ...args) {
            if (level <= Logger.LEVEL) {
                log(Logger.LEVELSTRS[level], msg, ...args);
            }
        };
        Logger.normal = function (msg, ...args) {
            Logger.out(msg, Logger.LEVELS.NORMAL, ...args);
        };
        Logger.error = function (msg, ...args) {
            console.trace();
            Logger.out(msg, Logger.LEVELS.ERROR, ...args);
        };
        Logger.exception = function (msg, ...args) {
            if (msg instanceof Error) {
                Logger.out(msg.stack, Logger.LEVELS.EXCEPTION);
            } else {
                console.trace();
            }
            Logger.out(msg, Logger.LEVELS.EXCEPTION, ...args);
        };
        Logger.warning = function (msg, ...args) {
            Logger.out(msg, Logger.LEVELS.WARNING, ...args);
        };
        Logger.info = function (msg, ...args) {
            Logger.out(msg, Logger.LEVELS.INFO, ...args);
        };
        Logger.debug = function (msg, ...args) {
            Logger.out(msg, Logger.LEVELS.DEBUG, ...args);
        };
    })();

    // 工具
    const Tool = {};
    (function () {
        (function () {
            // 监听URL操作
            const _historyWrap = function (type) {
                const orig = history[type];
                const e = new Event(type);
                return function () {
                    const rv = orig.apply(this, arguments);
                    e.arguments = arguments;
                    window.dispatchEvent(e);
                    return rv;
                };
            };
            // 替换原有window
            if (typeof unsafeWindow != "undefined") {
                unsafeWindow.history.pushState = _historyWrap("pushState");
                unsafeWindow.history.replaceState =
                    _historyWrap("replaceState");
            } else if (typeof window != "undefined") {
                window.history.pushState = _historyWrap("pushState");
                window.history.replaceState = _historyWrap("replaceState");
            }
        })();

        // 添加一个方法用以监听URL变化
        Tool.addUrlChangeEventListener = function (func) {
            if (typeof unsafeWindow != "undefined") {
                unsafeWindow.addEventListener("pushState", func);
                unsafeWindow.addEventListener("replaceState", func);
                unsafeWindow.addEventListener("popstate", func);
                unsafeWindow.addEventListener("hashchange", func);
            }
        };

        // 判断元素是否为dom
        Tool.isDOM = (function () {
            return typeof HTMLElement === "object"
                ? function (obj) {
                      return obj instanceof HTMLElement;
                  }
                : function (obj) {
                      return (
                          obj &&
                          typeof obj === "object" &&
                          obj.nodeType === 1 &&
                          typeof obj.nodeName === "string"
                      );
                  };
        })();

        // 通过Jquery选择一个元素
        Tool.getSelectFromJquery = function (obj) {
            if (
                !(obj instanceof String) &&
                !(obj instanceof jQuery) &&
                !Tool.isDOM(obj)
            ) {
                Logger.exception(obj);
                Logger.exception("参数需要为选择器文本、DOM节点或jquery节点！");
                return null;
            }
            return $(obj);
        };

        // 原生方式选择一个元素
        Tool.getSelectFromDOM = function (obj) {
            let res = null;
            if (!(obj instanceof String)) {
                res = document.querySelector(obj);
            } else if (Tool.isDOM(obj)) {
                res = obj;
            } else {
                Logger.exception(obj);
                Logger.exception("参数需要为选择器文本或DOM节点！");
                return null;
            }
            return res;
        };
    })();

    // TweetHtml工具 用于获取推文注入点及注入推文翻译
    const TweetHtml = {};
    (function () {
        // 切换静态节点
        TweetHtml.staticAnchorSwitch = function (
            anchors = null,
            switchTo = null,
        ) {
            let selem = document.querySelector("#" + CONST_VAL.static_elem_id);
            anchors = anchors || TweetHtml.parseAnchors;
            if (!anchors) {
                return;
            }
            // 识别静态节点
            if (!selem) {
                anchors.rootDom.parentNode.appendChild(anchors.staticElem);
            } else {
                if (selem != anchors.staticElem) {
                    selem.remove();
                    anchors.rootDom.parentNode.appendChild(anchors.staticElem);
                }
            }
            switchTo =
                switchTo === true ||
                (anchors.staticElem.style.display == "none" &&
                    switchTo === null);
            Logger.debug("静态节点切换", switchTo);
            if (switchTo) {
                anchors.staticElem.style.display = "";
                anchors.rootDom.style.display = "none";
            } else {
                anchors.staticElem.style.display = "none";
                anchors.rootDom.style.display = "";
            }
        };
        // 获取当前页ID
        TweetHtml.getNowTweetId = function () {
            let nowurl = window.location.href;
            // 判断是否为推文页
            if (nowurl.lastIndexOf("/status/") == -1) {
                // 不在推文页时返回null
                return null;
            }
            // 删除查询参数
            if (nowurl.lastIndexOf("?") != -1) {
                nowurl = nowurl.substr(0, nowurl.lastIndexOf("?"));
            }
            // 获取推文ID
            return nowurl.substr(nowurl.lastIndexOf("/") + 1);
        };
        // 显示所有敏感内容隐藏
        TweetHtml.showAllHide = function () {
            try {
                let elems = CSSAnchor.articleHides(CSSAnchor.rootElem());
                let count = 0;
                for (let j = 0; j < elems.length; j++) {
                    try {
                        if (
                            elems[j].textContent == "查看" ||
                            elems[j].textContent == "显示" ||
                            elems[j].textContent == "View"
                        ) {
                            elems[j].click();
                            count++;
                        }
                    } catch (e) {
                        Logger.exception("显示隐藏内容时异常 -> ", e);
                        return -1;
                    }
                }
                return count;
            } catch (error) {
                Logger.warning("敏感信息显示功能异常。");
                return 0;
            }
        };
        TweetHtml.CSSAnchor = CSSAnchor;
        TweetHtml.parseAnchors = null;
        // 译文解析（emoji转img、文本颜色）
        TweetHtml.textparse = function (text) {
            let options = {
                whiteList: {
                    a: ["style"],
                    code: [],
                    div: ["style"],
                    em: [],
                    h1: [],
                    h2: [],
                    h3: [],
                    h4: [],
                    h5: [],
                    h6: [],
                    hr: ["style"],
                    i: [],
                    img: ["src", "alt", "title", "width", "height", "style"],
                    small: [],
                    span: ["style"],
                    sub: [],
                    sup: [],
                    strong: [],
                    strike: [],
                    ul: ["style"],
                    ol: ["style"],
                    li: ["style"],
                    p: ["style"],
                    pre: [],
                },
            };
            const attributesCallback = function (icon, variant) {
                //emoji置换回调
                return {
                    title: "Emoji: " + icon + variant,
                    style: "height: 1em;width: 1em;margin: 0.05em 0.1em;vertical-align: -0.1em;",
                };
            };
            // XSS过滤
            text = filterXSS(text, options);
            // 文本处理
            text = text.replace(/(\\\\)/gi, "\\&sla; "); // 转义处理
            text = text.replace(/(\\#)/gi, "\\&jh; "); // 转义处理
            text = text.replace(/(\\@)/gi, "\\&AT; "); // 转义处理
            text = text.replace(
                /(\S*)(#[^\s#\!0-9]{1}\S*)/gi,
                '$1<a style="color:#1DA1F2;">$2</a>',
            ); // 话题颜色处理
            text = text.replace(
                /([\S]*)(@[A-Za-z0-9_]{4,15})/gi,
                '$1<a style="color:#1DA1F2;">$2</a>',
            ); // 提及颜色处理
            text = text.replace(
                /((https?|ftp|file):\/\/[-A-Za-z0-9+&@#/%?=~_|!:,.;]+[-A-Za-z0-9+&@#/%=~_|])/g,
                '<a style="color:#1DA1F2;">$1</a>',
            ); // 链接颜色处理
            text = text.replace(/([^\n]+)\n/gi, "<p>$1</p>"); // 行包裹
            text = text.replace(/\n/gi, "<br>\n"); // 纯换行处理
            text = text.replace(/(\\&jh; )/gi, "#"); // 反转义
            text = text.replace(/(\\&AT; )/gi, "@"); // 反转义
            text = text.replace(/(\\&sla; )/gi, "\\"); // 反转义
            return twemoji.parse(text, {
                attributes: attributesCallback,
                base: "https://abs-0.twimg.com/emoji/v2/",
                folder: "svg",
                ext: ".svg",
            }); // 处理emoji
        };
        // 获取注入点信息组
        TweetHtml.getAnchors = function () {
            /*
                [
                    [
                        {
                            dom: elart,  // 推文主体
                            textAnchors: [  // 推文的文本节点
                                {
                                    dom: elemtexts[j],
                                    text: elemtexts[j].innerText,
                                }
                            ],
                            imgAnchors: [  // 推文的图片节点
                                {
                                    dom: elemimgs[j],
                                    href: elemimgs[j].href,
                                    imgdom:imgdom,
                                    imgsrc: (imgdom == null?"":imgdom.src)
                                }
                            ],
                            voteAnchors: [  // 推文投票节点
                                {
                                    dom: elemvotes[j],
                                    text: elemvotes[j].innerText,
                                }
                            ],
                            endAnchor: null,
                        },
                    ]
                ]
             */
            // 静态元素
            let staticElem = document.createElement("div");
            staticElem.id = CONST_VAL.static_elem_id;
            staticElem.style.display = "none";
            let staticMainElem = document.createElement("div");
            staticMainElem.id = CONST_VAL.static_elem_id + "_main";
            let staticReplayElem = document.createElement("div");
            staticReplayElem.id = CONST_VAL.static_elem_id + "_replay";
            staticElem.appendChild(staticMainElem);
            staticElem.appendChild(staticReplayElem);
            // 主元素
            let rootDom = CSSAnchor.rootElem(document);
            if (!rootDom) {
                return [false, "推文不存在"];
            }
            // 推文集
            let articles = CSSAnchor.articles(rootDom);
            if (articles.length == 0) {
                return [false, "未发现推文，请重试"];
            }

            //注入点收集表
            let tweetAnchors = [];
            let tweetAnchor = [];
            let mainTweet = true;
            //搜索可注入元素
            for (var i = 0; 1 == 1; i++) {
                //发现元素不存在时
                if (typeof articles[i] == "undefined") {
                    if (!mainTweet) {
                        break;
                    }
                    return [false, "未搜索到推文结束位置，请联系制作者反馈！"];
                }
                //搜索推文
                let elart = articles[i];
                if (elart) {
                    elart = elart.cloneNode(true);
                    if (mainTweet) {
                        staticMainElem.append(elart);
                    } else {
                        elart.style.display = "none";
                        staticReplayElem.append(elart);
                    }
                    // 初始化item
                    let elartItem = {
                        dom: elart,
                        textAnchors: [],
                        imgAnchors: [],
                        voteAnchors: [],
                        endAnchor: null,
                    };
                    // 搜索可注入的文本锚点
                    let elemtexts = CSSAnchor.articleTexts(elart);
                    for (let j = 0; j < elemtexts.length; j++) {
                        elartItem.textAnchors.push({
                            dom: elemtexts[j],
                            text: elemtexts[j].innerText,
                        });
                    }
                    // 搜索可注入的图片锚点
                    let elemimgs = CSSAnchor.articleImages(elart);
                    for (let j = 0; j < elemimgs.length; j++) {
                        let imgdom = CSSAnchor.articleInImage(elemimgs[j]);
                        elartItem.imgAnchors.push({
                            dom: elemimgs[j],
                            href: elemimgs[j].href,
                            imgdom: imgdom,
                            imgsrc: imgdom == null ? "" : imgdom.src,
                        });
                    }
                    // 搜索可注入的投票锚点
                    let elemvotes = CSSAnchor.articleVotes(elart);
                    for (let j = 0; j < elemvotes.length; j++) {
                        elartItem.voteAnchors.push({
                            dom: elemvotes[j],
                            text: elemvotes[j].innerText,
                        });
                    }
                    //检测推文是否结束
                    if (mainTweet) {
                        // 检索翻译推文按钮
                        let transNotice = CSSAnchor.transNotice(elart);
                        if (transNotice) {
                            transNotice.remove();
                        }
                        let endAnchor = null;
                        if (!endAnchor) {
                            //转推喜欢
                            endAnchor = CSSAnchor.articleRetweetLike(elart);
                            if (endAnchor) {
                                endAnchor.remove();
                            }
                        }
                        if (!endAnchor) {
                            //时间
                            endAnchor = CSSAnchor.articleTime(elart);
                        }
                        if (endAnchor) {
                            mainTweet = false;
                            elartItem.endAnchor = endAnchor;
                        }
                    }
                    tweetAnchor.push(elartItem);
                    if (!mainTweet) {
                        tweetAnchors.push(tweetAnchor);
                        tweetAnchor = [];
                        continue;
                    }
                }
            }
            return [
                true,
                "成功！",
                {
                    staticElem: staticElem,
                    rootDom: rootDom,
                    tweetAnchors: tweetAnchors,
                },
            ];
        };
        // 等待图片加载
        TweetHtml.waitImageComplate = function (
            timeout = 15000,
            addTimeCallback = null,
        ) {
            return new Promise(function (resolve, reject) {
                let rootDom = CSSAnchor.rootElem();
                //判断图片是否加载完成
                let imgIsAllLoadComplete = function () {
                    let photos = CSSAnchor.articleImages(rootDom);
                    if (photos.length == 0) {
                        Logger.info("未找到可加载图片");
                        return true;
                    }
                    for (let i = 0; i < photos.length; i++) {
                        let img = photos[i].querySelector("img");
                        try {
                            if (img == null || !img.complete) {
                                return false;
                            }
                        } catch (e) {
                            Logger.exception(e);
                            return true;
                        }
                    }
                    return true;
                };
                let waitTimeCount = 0;
                let checkloop = function () {
                    waitTimeCount += 100;
                    if (addTimeCallback) {
                        addTimeCallback(100);
                    }
                    if (waitTimeCount > timeout) {
                        reject("等待超时！");
                        return;
                    }
                    if (!imgIsAllLoadComplete()) {
                        setTimeout(checkloop, 100);
                    } else {
                        resolve();
                    }
                };
                // 启动检查循环
                setTimeout(checkloop, 100);
            });
        };

        // 推特加载等待
        TweetHtml.waitLoad = function (
            loadComplateFunc,
            timeout = 15000,
            showHide = true,
        ) {
            let waitTimeCount = 0;
            let waitRootDom = function () {
                return new Promise(function (resolve, reject) {
                    let checkloop = function () {
                        waitTimeCount += 100;
                        if (waitTimeCount > timeout) {
                            reject("等待超时！");
                            return;
                        }
                        if (CSSAnchor.rootElem() == null) {
                            let dom = CSSAnchor.twitterError();
                            if (dom) {
                                reject("推特错误：" + dom.textContent);
                                return;
                            }
                            setTimeout(checkloop, 100);
                        } else {
                            resolve();
                            return;
                        }
                    };
                    // 启动检查循环
                    setTimeout(checkloop, 100);
                });
            };
            let waitTweetLoad = function () {
                // 推文等待数
                const waitNum = 1;
                return new Promise(function (resolve, reject) {
                    let rootDom = CSSAnchor.rootElem();
                    let checkloop = function () {
                        waitTimeCount += 100;
                        if (waitTimeCount > timeout) {
                            reject("等待超时！");
                            return;
                        }
                        if (CSSAnchor.articles(rootDom).length < waitNum) {
                            setTimeout(checkloop, 100);
                        } else {
                            resolve();
                            return;
                        }
                    };
                    // 启动检查循环
                    setTimeout(checkloop, 100);
                });
            };
            let showAllHide = function () {
                return new Promise(function (resolve, reject) {
                    if (showHide) {
                        let count = TweetHtml.showAllHide();
                        if (count == 0) {
                            resolve();
                        } else {
                            // 给予页面渲染时间，使其可以加载必要数据（针对隐藏的媒体）
                            setTimeout(function () {
                                resolve();
                            }, 100);
                        }
                    } else {
                        resolve();
                    }
                });
            };
            let waitNeedWait = function () {
                return new Promise(function (resolve, reject) {
                    let checkloop = function () {
                        waitTimeCount += 100;
                        if (waitTimeCount > timeout) {
                            reject("等待超时！");
                            return;
                        }
                        if (CSSAnchor.twitterNeedWait()) {
                            setTimeout(checkloop, 100);
                        } else {
                            resolve();
                            return;
                        }
                    };
                    // 启动检查循环
                    setTimeout(checkloop, 100);
                });
            };
            let waitImageComplate = TweetHtml.waitImageComplate;

            waitRootDom()
                .then(function () {
                    Logger.debug("检测到根元素，计时：" + waitTimeCount + "ms");
                    return waitTweetLoad();
                })
                .then(function () {
                    Logger.debug("已等待到推文，计时：" + waitTimeCount + "ms");
                    return showAllHide();
                })
                .then(function () {
                    Logger.debug(
                        "隐藏内容已解锁，计时：" + waitTimeCount + "ms",
                    );
                    return waitNeedWait();
                })
                .then(function () {
                    Logger.debug(
                        "已等待所有需要等待的内容，计时：" +
                            waitTimeCount +
                            "ms",
                    );
                    return waitImageComplate(
                        timeout - waitTimeCount,
                        function (addTime) {
                            waitTimeCount += addTime;
                        },
                    );
                })
                .then(function () {
                    Logger.debug("图片加载完成，计时：" + waitTimeCount + "ms");
                    if (loadComplateFunc) {
                        loadComplateFunc(true);
                    }
                    return;
                })
                .catch(function (reason, data) {
                    if (data) {
                        Logger.warning("异常：", reason, data);
                    }
                    if (loadComplateFunc) {
                        loadComplateFunc(false, reason);
                    }
                });
        };
        // 推文解析
        TweetHtml.parsing = function () {
            let tweetId = TweetHtml.getNowTweetId();
            TweetHtml.tweetId = tweetId;
            if (tweetId) {
                if (TweetHtml.parseAnchors) {
                    TweetHtml.staticAnchorSwitch(TweetHtml.parseAnchors, false);
                }
                let parseAnchors = TweetHtml.getAnchors();
                if (!parseAnchors[0]) {
                    Logger.warning(parseAnchors[1]);
                    TweetHtml.parseAnchors = null;
                    return false;
                }
                TweetHtml.parseAnchors = parseAnchors[2];
                Logger.info("推文", tweetId, "解析成功");
                // Logger.debug(parseAnchors);
                return true;
            }
            return false;
        };
        const MARK_HIDE_CLASS = CONST_VAL.static_mark_hide; // 隐藏标记类，用于恢复隐藏的内容
        const MARKCLASS = CONST_VAL.static_insert_trans; // 注入标记类，用于清除注入内容
        // 注入翻译信息
        TweetHtml.insertTrans = function (
            tweetAnchors,
            trans,
            parseText = true,
        ) {
            /**
            trans结构
            {
                main_cover: false,  // 主推文覆盖
                replay_cover: false,  // 回复覆盖
                quote_cover: false,  // 转评覆盖
                template: template,  // 烤推模版(Html)
                levels: {   // 待注入的数据
                    1:{
                        key: 1,
                        content:"推文翻译",
                        inlevel:{
                            1:{
                                key: 1,
                                content:"引用推文翻译",
                            }
                        },  // 引用推文的配置
                        img:{},  // 图片覆盖
                        vote:{},  // 投票覆盖
                    },
                    2:...,
                    'last':...,  // 代表主推文
                    'main':...,  // 同last
                },
            }
            tweetAnchors由getAnchors生成
            */
            tweetAnchors =
                tweetAnchors ||
                (TweetHtml.parseAnchors && TweetHtml.parseAnchors.tweetAnchors);
            if (!tweetAnchors) {
                return [false, "未进行推文解析，或推文解析失败。", null];
            }
            const TRANSTEXTCLASS = CONST_VAL.static_insert_tran_text; // 翻译文本
            const TRANSTYPECLASS = CONST_VAL.static_insert_tran_type; // 翻译标识
            const TRANSMEDIACLASS = CONST_VAL.static_insert_tran_media; // 媒体
            const TRANSVOTECLASS = CONST_VAL.static_insert_tran_vote; // 投票
            try {
                // 获取覆盖配置
                let coverconfig = {
                    replay_cover: trans.replay_cover || false,
                    quote_cover: trans.quote_cover || false,
                    main_cover: trans.main_cover || false,
                    template_disable: trans.template_disable || false,
                };
                // 创建DOM的函数 tweettext transtype
                let createInsertDom = function (type, data) {
                    let dom = document.createElement("div");
                    let indom = null;
                    dom.className = MARKCLASS;
                    dom.style = CONST_VAL.tran_main_style;
                    if (type == "tweettext") {
                        indom = document.createElement("div");
                        indom.className = TRANSTEXTCLASS;
                        indom.style = CONST_VAL.tran_text_style;
                        indom.innerHTML = data;
                        dom.appendChild(indom);
                    } else if (type == "transtype") {
                        indom = document.createElement("div");
                        indom.className = TRANSTYPECLASS;
                        indom.style = CONST_VAL.tran_type_style;
                        if (trans.template_disable || trans.main_cover) {
                            indom.style += ";display: none;";
                        }
                        indom.innerHTML = data;
                        dom.appendChild(indom);
                    } else if (type == "media") {
                        indom = document.createElement("div");
                        indom.className = TRANSMEDIACLASS;
                        indom.style = CONST_VAL.tran_media_style;
                        indom.innerHTML = data;
                        dom.appendChild(indom);
                    } else if (type == "vote") {
                        indom = document.createElement("div");
                        indom.className = TRANSVOTECLASS;
                        indom.style = CONST_VAL.tran_vote_style;
                        indom.innerHTML = data;
                        dom.appendChild(indom);
                    }
                    return dom;
                };
                // 在指定元素后插入元素
                let insertAfter = function (newElement, targetElement) {
                    var parent = targetElement.parentNode;
                    if (parent.lastChild == targetElement) {
                        // 如果最后的节点是目标元素，则直接添加。因为默认是最后
                        parent.appendChild(newElement);
                    } else {
                        //如果不是，则插入在目标元素的下一个兄弟节点的前面。也就是目标元素的后面
                        parent.insertBefore(
                            newElement,
                            targetElement.nextSibling,
                        );
                    }
                };
                // 文本段注入 参数 覆盖标识，原始dom，新元素标识，新元素内容数据
                let insertTextData = function (
                    cover_flag,
                    sourcedom,
                    data,
                    isMain = false,
                ) {
                    if (parseText) {
                        data = TweetHtml.textparse(data);
                    }
                    if (isMain == false && cover_flag == false) {
                        data = "<p>--------</p>" + data;
                    }
                    let tempDom = createInsertDom("tweettext", data);
                    tempDom.className =
                        sourcedom.className + " " + tempDom.className;
                    // 添加隐藏标识
                    sourcedom.classList.add(MARK_HIDE_CLASS);
                    if (cover_flag) {
                        sourcedom.style.display = "none";
                    } else {
                        sourcedom.style.display = "block";
                    }
                    insertAfter(tempDom, sourcedom);
                    return tempDom;
                };
                // 媒体注入 参数 原始dom，新元素标识，新元素内容数据
                let insertMediaData = function (sourcedom, data) {
                    if (parseText) {
                        data = TweetHtml.textparse(data);
                    }
                    let tempDom = createInsertDom("media", data);
                    sourcedom.innerHTML = "";
                    sourcedom.appendChild(tempDom);
                    return tempDom;
                };
                // 投票注入 参数 原始dom，元素标识，元素内容
                let insertVoteData = function (sourcedom, data) {
                    if (parseText) {
                        data = TweetHtml.textparse(data)
                            .replace("\n", "")
                            .replace("<br>", "")
                            .replace("<br/>", "")
                            .trim();
                    }
                    let tempDom = createInsertDom("vote", data);
                    sourcedom.innerHTML = "";
                    sourcedom.appendChild(tempDom);
                    return tempDom;
                };
                // 翻译标识注入 参数 原始dom，元素标识，元素内容
                let insertTransFlag = function (sourcedom, data) {
                    if (parseText) {
                        data = TweetHtml.textparse(data);
                    }
                    let tempDom = createInsertDom("transtype", data);
                    tempDom.className =
                        sourcedom.className + " " + tempDom.className;
                    insertAfter(tempDom, sourcedom);
                    return tempDom;
                };
                // 推文计数
                let elartCount = 0;
                let inTweetAnchors;
                let tweetAnchor;
                let tranlevel;

                // 注入预处理
                if (trans.levels["last"] || trans.levels["main"]) {
                    if (!trans.levels[tweetAnchors[0].length]) {
                        // last存在且没有显示定义主元素翻译内容则使用last内容替换主元素翻译内容
                        trans.levels[tweetAnchors[0].length] =
                            trans.levels["last"] || trans.levels["main"];
                    }
                }

                for (let i = 0; i < tweetAnchors.length; i++) {
                    inTweetAnchors = tweetAnchors[i];
                    for (let j = 0; j < inTweetAnchors.length; j++) {
                        // 遍历推文注入点
                        // 当 i == 1 时存在特殊注入点last或main，用于主推文置入
                        tweetAnchor = inTweetAnchors[j];
                        elartCount++;
                        // 检查注入点
                        if (!trans.levels[elartCount]) {
                            if (i != 0) {
                                tweetAnchor.dom.style.display = "none";
                            }
                            continue;
                        }
                        tranlevel = trans.levels[elartCount];
                        if (i != 0) {
                            tweetAnchor.dom.style.display = "";
                        }
                        // 开始注入

                        // 文本注入
                        if (tweetAnchor.textAnchors[0]) {
                            if (i == 0 && j == inTweetAnchors.length - 1) {
                                // 主元素
                                let dom = insertTransFlag(
                                    tweetAnchor.textAnchors[0].dom,
                                    trans.template || "",
                                );
                                // 仅覆盖原文时使用原文坐标，非覆盖情况下使用注入标签后的标签坐标
                                insertTextData(
                                    coverconfig.main_cover,
                                    coverconfig.main_cover
                                        ? tweetAnchor.textAnchors[0].dom
                                        : dom,
                                    tranlevel.content,
                                    true,
                                );
                            } else {
                                insertTextData(
                                    coverconfig.replay_cover,
                                    tweetAnchor.textAnchors[0].dom,
                                    tranlevel.content,
                                );
                            }
                        }
                        // 内嵌文本
                        if (tweetAnchor.textAnchors.length > 1) {
                            for (
                                let k = 1;
                                k < tweetAnchor.textAnchors.length;
                                k++
                            ) {
                                if (tweetAnchor.textAnchors[k]) {
                                    if (tranlevel.inlevel[k]) {
                                        insertTextData(
                                            coverconfig.quote_cover,
                                            tweetAnchor.textAnchors[k].dom,
                                            tranlevel.inlevel[k].content,
                                        );
                                    }
                                }
                            }
                        }

                        // 媒体注入（图片）
                        if (tweetAnchor.imgAnchors.length > 0) {
                            for (
                                let k = 0;
                                k < tweetAnchor.imgAnchors.length;
                                k++
                            ) {
                                if (tweetAnchor.imgAnchors[k]) {
                                    if (tranlevel.img[k + 1]) {
                                        insertMediaData(
                                            tweetAnchor.imgAnchors[k].dom,
                                            tranlevel.img[k + 1].content,
                                        );
                                    }
                                }
                            }
                        }
                        // 投票注入
                        if (tweetAnchor.voteAnchors.length > 0) {
                            for (
                                let k = 0;
                                k < tweetAnchor.voteAnchors.length;
                                k++
                            ) {
                                if (tweetAnchor.voteAnchors[k]) {
                                    if (tranlevel.vote[k + 1]) {
                                        insertVoteData(
                                            tweetAnchor.voteAnchors[k].dom,
                                            tranlevel.vote[k + 1].content,
                                        );
                                    }
                                }
                            }
                        }
                    }
                }

                // 后处理 给P元素指定通用样式
                let p_style =
                    "margin-bottom: 0px;margin-left: 0px;margin-right: 0px;margin-top: 0px;padding-bottom: 0px;padding-left: 0px;padding-right: 0px;padding-top: 0px;";
                let doms = document.querySelectorAll(
                    "." + TRANSTEXTCLASS + " p:not([style])",
                );
                for (let ti = 0; ti < doms.length; ti++) {
                    doms[ti].style = p_style;
                }
                doms = document.querySelectorAll(
                    "." + TRANSTYPECLASS + " p:not([style])",
                );
                for (let ti = 0; ti < doms.length; ti++) {
                    doms[ti].style = p_style;
                }
                return [true, "成功", null];
            } catch (error) {
                Logger.exception(error);
                return [false, "注入翻译时异常", error.toString()];
            }
        };
        // 移除所有注入
        TweetHtml.removeAllInsert = function () {
            let alldoms = document.querySelectorAll(
                "." + MARKCLASS.replace(/\s+/g, "."),
            );
            alldoms.forEach(function (item) {
                item.remove();
            });
            alldoms = document.querySelectorAll(
                "." + MARK_HIDE_CLASS.replace(/\s+/g, "."),
            );
            alldoms.forEach(function (item) {
                item.style.display = "block";
            });
        };
        // 文本方式解析
        TweetHtml.parsingArgStr = function (
            argstr,
            template = "<p>翻译自日语</p>",
        ) {
            /**
            标记模式
            配置项 覆盖模式，默认不覆盖原文
            起始标记
            ##标记 内容
            节点标记规则：层数(指定层译文),层数+1(层内层翻译),last(主推文，默认标识亦是),config(配置)
            中文标记:x/层x/第x层、回复x、层内x/引用x/内嵌x、图片x、选项x/投票x、(不)覆盖、回复(不)覆盖、引用(不)覆盖
             */
            /**
            trans结构{
                main_cover: false,  // 主推文覆盖
                replay_cover: false,  // 回复覆盖
                quote_cover: false,  // 转评覆盖
                template_disable: false, // 无模版
                template: template,  // 烤推模版(Html)
                levels: {
                    1:{
                        key: 1,
                        content:"推文翻译",
                        inlevel:{
                            1:{
                                key: 1,
                                content:"引用推文翻译",
                            }
                        },  // 引用推文的配置
                        img:{},  // 图片覆盖
                        vote:{},  // 投票覆盖
                    },
                    2:...,
                    'last':...,  // 代表主推文
                    'main':...,  // 同last
                },
            }
             */
            let trans = {
                template: template,
                levels: {},
            };
            let idIter = function () {
                let oid = 1;
                return function () {
                    return oid++;
                };
            };
            let getNewLevel = idIter();
            let getInLevel = idIter();
            let getImgLevel = idIter();
            let getVoteLevel = idIter();
            // 标记正则表
            let MARKS = {
                level: [
                    {
                        mark: "level",
                        expre: /^last/,
                        default: () => "last",
                        value: (match) => null,
                    },
                    {
                        mark: "level",
                        expre: /^层([0-9]*)/,
                        default: () => getNewLevel(),
                        value: (match) => match[1],
                    },
                    {
                        mark: "level",
                        expre: /^第([0-9]*)层/,
                        default: () => getNewLevel(),
                        value: (match) => match[1],
                    },
                    {
                        mark: "level",
                        expre: /^回复([0-9]*)/,
                        default: () => getNewLevel(),
                        value: (match) => match[1] && parseInt(match[1]) + 1,
                    },
                    {
                        mark: "level",
                        expre: /^([0-9]+)/,
                        default: () => getNewLevel(),
                        value: (match) => match[1],
                    },
                ],
                inlevel: [
                    {
                        mark: "inlevel",
                        expre: /^层内([0-9]*)/,
                        default: () => getInLevel(),
                        value: (match) => match[1],
                    },
                    {
                        mark: "inlevel",
                        expre: /^引用([0-9]*)/,
                        default: () => getInLevel(),
                        value: (match) => match[1],
                    },
                    {
                        mark: "inlevel",
                        expre: /^内嵌([0-9]*)/,
                        default: () => getInLevel(),
                        value: (match) => match[1],
                    },
                ],
                img: [
                    {
                        mark: "img",
                        expre: /^图片([0-9]*)/,
                        default: () => getImgLevel(),
                        value: (match) => match[1],
                    },
                ],
                vote: [
                    {
                        mark: "vote",
                        expre: /^投票([0-9]*)/,
                        default: () => getVoteLevel(),
                        value: (match) => match[1],
                    },
                    {
                        mark: "vote",
                        expre: /^选项([0-9]*)/,
                        default: () => getVoteLevel(),
                        value: (match) => match[1],
                    },
                ],
                config: [
                    {
                        mark: "config",
                        expre: /^回复覆盖|覆盖回复/,
                        default: () => true,
                        value: (match) => "replay_cover",
                    },
                    {
                        mark: "config",
                        expre: /^转评覆盖|覆盖转评|引用覆盖|覆盖引用|内嵌覆盖|覆盖内嵌/,
                        default: () => true,
                        value: (match) => "quote_cover",
                    },
                    {
                        mark: "config",
                        expre: /^回复不覆盖|不覆盖回复/,
                        default: () => false,
                        value: (match) => "replay_cover",
                    },
                    {
                        mark: "config",
                        expre: /^转评不覆盖|不覆盖转评|引用不覆盖|不覆盖引用|内嵌不覆盖|不覆盖内嵌/,
                        default: () => false,
                        value: (match) => "quote_cover",
                    },
                    {
                        mark: "config",
                        expre: /^无模版|无模板|无logo/,
                        default: () => true,
                        value: (match) => "template_disable",
                    },
                    // 特殊属性
                    {
                        mark: "config",
                        expre: /^全覆盖|全部覆盖|覆盖全部|覆盖全/,
                        default: () => "all_cover",
                        value: (match) => true,
                    },
                    {
                        mark: "config",
                        expre: /^全不覆盖|全部不覆盖|不覆盖全部|不覆盖全/,
                        default: () => "all_cover",
                        value: (match) => false,
                    },
                    {
                        mark: "config",
                        expre: /^模版|模板|logo/,
                        default: () => "template",
                        value: (match) => "template",
                    },
                    {
                        mark: "config",
                        expre: /^烤推模版|烤推模板/,
                        default: () => "template",
                        value: (match) => "template",
                    },
                    {
                        mark: "config",
                        expre: /^默认模版|默认模板/,
                        default: () => "defalutTemplate",
                        value: (match) => "template",
                    },
                    {
                        mark: "config",
                        expre: /^(推文)?覆盖(推文)?/,
                        default: () => true,
                        value: (match) => "main_cover",
                    },
                    {
                        mark: "config",
                        expre: /^(推文)?不覆盖(推文)?/,
                        default: () => false,
                        value: (match) => "main_cover",
                    },
                ],
            };
            let createNewLevel = function () {
                return {
                    key: -1,
                    content: "",
                    config: {},
                    inlevel: {},
                    img: {},
                    vote: {},
                };
            };
            let spargs;
            spargs = argstr.trim().split("##");
            let nowstr;
            let level = createNewLevel();
            for (let i = 0; i < spargs.length; i++) {
                nowstr = spargs[i].trim();
                if (nowstr == "") {
                    continue;
                }
                // 匹配到的mark
                let markitem = null;
                if (i == 0) {
                    markitem = {
                        mark: "level",
                        expre: /(.+)/,
                        default: () => "last",
                        value: (match) => null,
                    };
                    markitem.result = markitem.default();
                    markitem.content = nowstr;
                }
                try {
                    if (markitem == null) {
                        let mark_list = ["config", "level", "inlevel", "vote", "img"]
                        for (let mark_i in mark_list) {
                            let mark = mark_list[mark_i];
                            for (let ii = 0; ii < MARKS[mark].length; ii++) {
                                let matchitem = MARKS[mark][ii];
                                let match = nowstr.match(matchitem.expre);
                                if (match) {
                                    // 使用item覆盖减少内存使用的同时区分原item
                                    markitem = Object.assign({}, matchitem);
                                    markitem.result = matchitem.value(match);
                                    if (!markitem.result) {
                                        markitem.result = matchitem.default();
                                    }
                                    markitem.content = nowstr
                                        .replace(matchitem.expre, "")
                                        .trim();
                                    break;
                                }
                            }
                            if (markitem) {
                                break;
                            }
                        }
                    }
                    if (markitem == null) {
                        markitem = {
                            mark: "level",
                            expre: /(.+)/,
                            default: () => getNewLevel(),
                            value: (match) => null,
                        };
                        markitem.result = markitem.default();
                        markitem.content = nowstr;
                    }
                    if (markitem.mark == "level") {
                        // 将处理好的元素放进层列表中
                        if (level.key != -1) {
                            trans.levels[level.key] = level;
                        }
                        // 更新自动计数器
                        getInLevel = idIter();
                        getImgLevel = idIter();
                        getVoteLevel = idIter();
                        // 创建新元素
                        level = createNewLevel();
                        level.key = markitem.result;
                        level.content = markitem.content;
                        continue;
                    } else if (markitem.mark == "config") {
                        if (markitem.default() === "template") {
                            trans[markitem.result] = markitem.content;
                        } else if (markitem.default() === "defalutTemplate") {
                            if (!trans[markitem.result]) {
                                // 默认模版不覆盖已有值
                                trans[markitem.result] =
                                    markitem.content.trim();
                            }
                        } else if (markitem.default() === "all_cover") {
                            trans["main_cover"] = markitem.result;
                            trans["replay_cover"] = markitem.result;
                            trans["quote_cover"] = markitem.result;
                        } else {
                            trans[markitem.result] = markitem.default();
                        }
                        continue;
                    }
                    level[markitem.mark][markitem.result] = {
                        key: markitem.result,
                        content: markitem.content,
                    };
                } catch (error) {
                    Logger.warning("匹配 ", nowstr, " 时异常");
                    Logger.exception(error);
                }
            }
            // 尾处理
            if (level.key != -1) {
                trans.levels[level.key] = level;
            }
            return trans;
        };
        // 移除影响使用体验的元素
        TweetHtml.removeSomeDom = function () {
            let dom;
            // 移除底栏
            dom = TweetHtml.CSSAnchor.twitterBottomBar();
            if (dom) {
                dom.remove();
            }
            // 移除登录提示框
            dom = TweetHtml.CSSAnchor.twitterDialog();
            if (dom) {
                // 恢复滚动条
                document.querySelector("html").style.overflowY = "scroll";
                dom.remove();
            }
        };
    })();

    function tweetCoreInit() {
        // 核心初始化
        // 提供给控制台的函数
        let transSwitch = function (showSource) {
            /**
             * 切换原文与烤推文本
             */
            return TweetHtml.staticAnchorSwitch(null, showSource);
        };
        let consoleTest = function (text, template = "<p>翻译自日语</p>") {
            /**
             * 烤推
             *
             * 参数：待解析文本，模版
             */
            TweetHtml.removeAllInsert();
            transSwitch(true);
            return TweetHtml.insertTrans(
                null,
                TweetHtml.parsingArgStr(text, template),
            );
        };

        // 将部分函数函数注册到全局
        if (typeof unsafeWindow != "undefined") {
            Logger.info("已注册`TweetHtml`至全局(unsafeWindow)");
            unsafeWindow.TweetHtml = TweetHtml;
            unsafeWindow.trans = consoleTest;
            unsafeWindow.transSwitch = transSwitch;
        }
        if (typeof window != "undefined") {
            Logger.info("已注册`TweetHtml`至全局(window)");
            window.TweetHtml = TweetHtml;
            window.trans = consoleTest;
            window.transSwitch = transSwitch;
        }
        // 进行初始解析
        if (CONFIG_CORE.AUTO_LOAD) {
            if (TweetHtml.getNowTweetId()) {
                TweetHtml.parsing();
                // TweetHtml.staticAnchorSwitch(null, true);
                Logger.info(
                    "一切准备就绪可使用`trans(烤推文本,模版)`方法进行翻译，使用`transSwitch(true/false)`方法切换原文档与翻译文档",
                );
            } else {
                Logger.info(
                    "烤推未就绪，切换到推文页面后可使用`trans(烤推文本,模版)`方法进行翻译，使用`transSwitch(true/false)`方法切换原文档与翻译文档",
                );
            }
        }
        if (CONFIG_CORE.URL_CHECK_ENALBE) {
            let hasParsing = false;
            Tool.addUrlChangeEventListener(function (e) {
                let tweetId = TweetHtml.getNowTweetId();
                Logger.debug(
                    "页面URL变化 ->",
                    window.location.href,
                    ";推文ID解析=",
                    tweetId,
                );
                if (tweetId == null) {
                    TweetHtml.parseAnchors = null;
                }
                if (!hasParsing) {
                    TweetHtml.waitLoad(function (isOK, reason) {
                        hasParsing = true;
                        setTimeout(function () {
                            TweetHtml.parsing();
                            if (isOK) {
                                Logger.info("烤推已就绪");
                            } else {
                                Logger.info(
                                    "烤推解析失败，或许需要切换到推文页。原因：",
                                    reason,
                                );
                            }
                            hasParsing = false;
                        }, 1);
                    }, 1500);
                }
            });
        }
    }

    function UIInit() {
        // TweetHtml.loopShowHide();
        // URL变化时更新状态
        // UI初始化
    }

    function main(isOK, reason) {
        if (!isOK) {
            Logger.info("读取推文信息失败，原因：" + reason);
        } else {
            Logger.info("已完成加载等待√");
        }
        tweetCoreInit();
        Logger.debug("核心初始化完成...");
        if (CONFIG_CORE.UI_ENALBE) {
            UIInit();
            Logger.debug("UI初始化完成...");
        } else {
            Logger.info("已跳过UI初始化！");
        }
    }
    // 等待推特加载完成后运行主函数
    if (CONFIG_CORE.RUN_MAIN && !GLOBAL_TOOL.ENABLE_PLAYWRIGHT) {
        Logger.info("====等待推文加载====");
        TweetHtml.waitLoad(main, CONFIG_CORE.START_WAIT_TIME * 1000);
    }
    if (GLOBAL_TOOL.ENABLE_PLAYWRIGHT) {
        // 注册脚本函数
        GLOBAL_TOOL.TweetHtml = TweetHtml;
        GLOBAL_TOOL.Tool = Tool;
        GLOBAL_TOOL.Logger = Logger;
        GLOBAL_TOOL.CSSAnchor = CSSAnchor;
    }
})();

// `playwright`自动化支持
if (GLOBAL_TOOL.ENABLE_PLAYWRIGHT) {
    function twitterWaitLoad(timeout) {
        return new Promise((resolve) => {
            return GLOBAL_TOOL.TweetHtml.waitLoad(
                (isOK, reason) => resolve([isOK, reason]),
                timeout,
            );
        });
    }

    async function playwright() {
        try {
            // 等待推文加载
            let result = await twitterWaitLoad(GLOBAL_TOOL.WAIT_TIMEOUT * 1000);
            if (!result[0]) {
                return [false, result[1], result];
            }
            // 推文解析
            GLOBAL_TOOL.TweetHtml.parsing();
            // 显示静态元素
            GLOBAL_TOOL.TweetHtml.staticAnchorSwitch(null, true);
            // 移除影响元素
            GLOBAL_TOOL.TweetHtml.removeSomeDom();
        } catch (e) {
            return [false, "未知报错", e.toString()];
        }
        GLOBAL_TOOL.Logger.info("文本：", GLOBAL_TOOL.TRANS_STR);
        GLOBAL_TOOL.Logger.info("字典：", GLOBAL_TOOL.TRANS_DICT);
        try {
            if (GLOBAL_TOOL.TRANS_DICT) {
                let rtnVal = GLOBAL_TOOL.TweetHtml.insertTrans(
                    null,
                    GLOBAL_TOOL.TRANS_DICT,
                );
                try {
                    await GLOBAL_TOOL.TweetHtml.waitImageComplate(15000);
                } catch (e) {
                    GLOBAL_TOOL.Logger.warning("等待时报错：" + e.toString());
                }
                
                return rtnVal;
            } else {
                let rtnVal = GLOBAL_TOOL.TweetHtml.insertTrans(
                    null,
                    GLOBAL_TOOL.TweetHtml.parsingArgStr(
                        GLOBAL_TOOL.TRANS_STR,
                        null,
                    ),
                );
                try {
                    await GLOBAL_TOOL.TweetHtml.waitImageComplate(15000);
                } catch (e) {
                    GLOBAL_TOOL.Logger.warning("等待时报错：" + e.toString());
                }
                return rtnVal;
            }
        } catch (e) {
            GLOBAL_TOOL.Logger.info("未知报错：" + e.toString());
            return [false, "未知报错", e.toString()];
        }
    }
    return playwright();
}
