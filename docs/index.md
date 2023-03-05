# Welcome to MkDocs

For full documentation visit [mkdocs.org](https://www.mkdocs.org).

## Commands

* `mkdocs new [dir-name]` - Create a new project.
* `mkdocs serve` - Start the live-reloading docs server.
* `mkdocs build` - Build the documentation site.
* `mkdocs -h` - Print help message and exit.

## Project layout

    mkdocs.yml    # The configuration file.
    docs/
        index.md  # The documentation homepage.
        ...       # Other markdown pages, images and other files.

### 参考

[参考链接](https://squidfunk.github.io/mkdocs-material/reference/)

### 醒目提示

!!! note "这是 note 类型的提示框"

    一种提示

!!! success "这是 success 类型的提示框"

    成功！

!!! failure "这是 failure 类型的提示框"

    失败！

!!! bug "这是 bug 类型的提示框"

    发现一个 bug，请尽快修复！

??? note "这是 note 类型的提示框"

    第一行

    第二行

    第三行

    第四行

    第五行

    ...

### 带标题的代码块及神奇代码注释

```python title='demo.py'
    def sayhi():
        return "hi,Python全栈开发"  # (1)
```

1. :man_raising_hand: 这是一行注释（

### 工具标题(tooltip)

[Hover me][example]

  [example]: https://example.com "I'm a tooltip!"

### 按钮？

[Subscribe to our newsletter](#按钮){ .md-button }

[Send :fontawesome-solid-paper-plane:](#commands){ .md-button }

### 分组Tab

=== "C"

    ``` c
    #include <stdio.h>

    int main(void) {
      printf("Hello world!\n");
      return 0;
    }
    ```

=== "C++"

    ``` c++
    #include <iostream>

    int main(void) {
      std::cout << "Hello world!" << std::endl;
      return 0;
    }
    ```

## generated

::: src.plugins.os_bot_base

::: src.plugins.os_bot_base.blacklist

::: src.plugins.os_bot_base.depends

::: src.plugins.os_bot_base.failover
