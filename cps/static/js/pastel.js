/* global $ */
/* Use the bundled Infinite Scroll and Isotope with caliBlur's scrolling pane. */
$(function () {
    $(document).on("click", ".pastel-book-back", function (event) {
        if (document.referrer && new URL(document.referrer).origin === window.location.origin && window.history.length > 1) {
            event.preventDefault();
            window.history.back();
        }
    });
    var curated = $(".curated-grid").length > 0;
    var paginationSelector = curated ? ".curated-pagination" : ".pagination";
    var $grid = $(curated ? ".curated-grid" : ".caliblur-index.load-more > .row");
    var $pagination = $(".col-sm-10 > " + paginationSelector);
    var $pane = $grid.closest(".col-sm-10");
    if (!$grid.length || !$pagination.find(".next").length || !$.fn.infiniteScroll) {
        return;
    }

    $grid.infiniteScroll({
        path: paginationSelector + " .next",
        append: curated ? ".curated-card" : ".load-more .book",
        elementScroll: $pane[0],
        outlayer: $grid.data("isotope"),
        history: false,
        scrollThreshold: 300
    });
    $pagination.addClass("pastel-infinite-active");
    $grid.on("append.infiniteScroll", function (event, response, path, items) {
        // Keep real navigation up to date for recovery after a network error.
        $pagination.html($(response).find(paginationSelector).html() || "");
        $(items).find("a[data-toggle='modal']").removeAttr("data-toggle");
        $(document).trigger("pastel:books-appended");
    });
    $grid.on("error.infiniteScroll", function () {
        $pagination.removeClass("pastel-infinite-active");
    });
});
