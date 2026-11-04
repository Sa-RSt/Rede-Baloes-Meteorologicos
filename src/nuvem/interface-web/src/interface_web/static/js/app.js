(function ($) {
  "use strict";

  $(function () {
    // Collapse every station branch except the one being viewed.
    $(".station-tree-node").each(function () {
      var $node = $(this);
      var isOpen = $node.hasClass("is-current");

      $node.toggleClass("is-open", isOpen);
      $node.find("> .station-tree-toggle").attr("aria-expanded", isOpen ? "true" : "false");
      $node.children(".station-tree-leaves").toggle(isOpen);
    });

    // Expand/collapse a station when its name is clicked.
    $(".station-tree-toggle").on("click", function () {
      var $button = $(this);
      var $node = $button.closest(".station-tree-node");
      var isOpen = !$node.hasClass("is-open");

      $node.toggleClass("is-open", isOpen);
      $button.attr("aria-expanded", isOpen ? "true" : "false");
      $node.children(".station-tree-leaves").stop(true, true).slideToggle(150);
    });

    // Keep the active leaf visible inside the scrollable tree panel.
    var $activeLeaf = $(".station-tree-leaf.active");
    if ($activeLeaf.length) {
      var $tree = $activeLeaf.closest(".station-tree");
      var leafTop = $activeLeaf.position().top + $tree.scrollTop();
      if (leafTop > $tree.height() - 40) {
        $tree.scrollTop(leafTop - $tree.height() + 60);
      }
    }
  });
})(jQuery);
