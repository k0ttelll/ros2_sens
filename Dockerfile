FROM osrf/ros:humble-desktop

# Отключаем интерактивные диалоги при установке
ENV DEBIAN_FRONTEND=noninteractive

# Устанавливаем базовые утилиты и зависимости для сборки
RUN apt-get update && apt-get install -y \
    tmux \
    terminator \
    python3-pip \
    python3-colcon-common-extensions \
    python3-rosdep \
    python3-networkx \
    python3-pydot \
    graphviz \
    git \
    python3-watchdog \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем Python-библиотеки для промышленных протоколов и вебхуков
RUN pip3 install python-snap7 asyncua flask watchdog

# Создаем рабочую директорию в контейнере
WORKDIR /root/ros2_ws

# Автоматически активируем ROS 2 во всех новых терминалах контейнера
RUN echo "source /opt/ros/humble/setup.bash" >> /root/.bashrc \
    && echo "if [ -f /root/ros2_ws/install/setup.bash ]; then source /root/ros2_ws/install/setup.bash; fi" >> /root/.bashrc

# Добавляем сохранение истории команд (чтобы стрелочка вверх работала после перезапуска)
RUN echo "export HISTFILE=/root/ros2_ws/.bash_history" >> /root/.bashrc \
    && echo "export HISTSIZE=1000" >> /root/.bashrc \
    && echo "export SAVEHIST=1000" >> /root/.bashrc

CMD ["bash"]
