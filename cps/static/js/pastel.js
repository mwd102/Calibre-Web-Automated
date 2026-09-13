/* global $ */
/* Use the bundled Infinite Scroll and Isotope with caliBlur's scrolling pane. */
$(function () {
    var $grid = $(".caliblur-index.load-more > .row");
    var $pagination = $(".col-sm-10 > .pagination");
    var $pane = $grid.closest(".col-sm-10");
    if (!$grid.length || !$pagination.find(".next").length || !$.fn.infiniteScroll) {
        return;
    }

    $grid.infiniteScroll({
        path: ".pagination .next",
        append: ".load-more .book",
        elementScroll: $pane[0],
        outlayer: $grid.data("isotope"),
        history: false,
        scrollThreshold: 300
    });
    $pagination.addClass("pastel-infinite-active");
    $grid.on("append.infiniteScroll", function (event, response, path, items) {
        // Keep real navigation up to date for recovery after a network error.
        $pagination.html($(response).find(".pagination").html() || "");
        $(items).find("a[data-toggle='modal']").removeAttr("data-toggle");
        $(document).trigger("pastel:books-appended");
    });
    $grid.on("error.infiniteScroll", function () {
        $pagination.removeClass("pastel-infinite-active");
    });
});
