// ==UserScript==
// @name         复旦一卡通导出 CSV 消费记录
// @namespace    http://tampermonkey.net/
// @version      0.2
// @description  复旦一卡通导出 CSV 消费记录
// @author       KAAAsS
// @match        https://ecard.fudan.edu.cn/epay/consume/*
// @icon         https://www.google.com/s2/favicons?sz=64&domain=fudan.edu.cn
// @grant        none
// ==/UserScript==

let $ = window.$ != undefined ? window.$ : null;

(function($) {
    'use strict';

    if (!$) return;

    const getTotalPage = () => {
        let el = document.body.innerHTML.match(/当前.*\/(\d+)页/);
        if (el == null) {
            return 1;
        }
        return parseInt(el[1]);
    };

    // Credit: https://stackoverflow.com/a/56370447
    function table_as_csv(table_el, separator = ',') {
        // Select rows from table_id
        var rows = table_el.querySelectorAll('tr');
        // Construct csv
        var csv = [];
        for (var i = 0; i < rows.length; i++) {
            var row = [], cols = rows[i].querySelectorAll('td, th');
            for (var j = 0; j < cols.length; j++) {
                // Clean innertext to remove multiple spaces and jumpline (break csv)
                var data = cols[j].innerText.replace(/(\r\n|\n|\r)/gm, '').replace(/(\s\s)/gm, ' ')
                // Escape double-quote with double-double-quote (see https://stackoverflow.com/questions/17808511/properly-escape-a-double-quote-in-csv)
                data = data.replace(/"/g, '""');
                // Push escaped string
                row.push('"' + data + '"');
            }
            // 增加一列订单号
            let $link = $(rows[i]).find('a');
            if ($link.length > 0) {
                let href = $link.attr('href');
                let tx_no = href.match("\\?billno=(\\d*)")[1];
                row.push(tx_no);
            } else {
                row.push('"订单号"');
            }

            csv.push(row.join(separator));
        }
        return csv;
    }

    Date.prototype.format = function(formatStr){
        var str = formatStr;
        var Week = ['日','一','二','三','四','五','六'];
        str=str.replace(/yyyy|YYYY/,this.getFullYear());
        str=str.replace(/MM/,(this.getMonth()+1)>9?(this.getMonth()+1).toString():'0' + (this.getMonth()+1));
        str=str.replace(/dd|DD/,this.getDate()>9?this.getDate().toString():'0' + this.getDate());
        return str;
    }

    function download_content(content) {
        let date = new Date().format("yyyyMMdd");
        var filename = 'FDU_' + date + '.csv';
        var link = document.createElement('a');
        link.style.display = 'none';
        link.setAttribute('target', '_blank');
        link.setAttribute('href', 'data:text/csv;charset=utf-8,' + encodeURIComponent(content));
        link.setAttribute('download', filename);
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }

    const sleep = ms => new Promise(r => setTimeout(r, ms));

    const waitPage = async (p) => {
        while (true) {
            let actual = $("#aazone\\.zone_show_box_1 b.fontred").text();
            if (actual == p)
                break;
            await sleep(10);
        }
    };

    const doParse = async () => {
        let total = getTotalPage();
        console.log(`总页数：${total}`);

        let csv = null;

        for (let page = 1; page <= total; page++) {
            console.log(`当前解析页面：${page}`);
            // 切换页面
            if (window.pageSubmit && total > 1) {
                window.pageSubmit(page, '1');
                await waitPage(page);
            }
            // 解析
            let $table = $("#aazone\\.zone_show_box_1>table");
            let ret = table_as_csv($table[0]);
            if (csv) {
                csv = csv.concat(ret.slice(1)); // 去除表头
            } else {
                csv = ret;
            }
        }

        let csv_content = csv.join("\n");
        download_content(csv_content);
    };

    $(function () {
        const $btnGroup = $('[type="submit"]').parent();
        const $btnExport = $('<input type="button" value="导    出" class="btn btn-primary">');

        if ($btnGroup) {
            console.log("找到按钮组，挂载 DOM");
            $btnGroup.append($btnExport);
            $btnExport.click(doParse);
        }
    });

    window.doParse = doParse;
})($);
